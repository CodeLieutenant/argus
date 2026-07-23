from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import BoundedSemaphore, Lock
from uuid import UUID

from argusAI.prompts import load_prompt

from .summarizer import DEFAULT_PROMPT, Summarizer, SummarizerError

LOGGER = logging.getLogger(__name__)

_SCT_EVENT_TABLE = "sct_event"
_STATS_LOG_EVERY = 50  # emit a rolling aggregate line every N completed summarizations


def _lag_seconds(ts: datetime) -> float:
    """Seconds from the event's timestamp to now — the summarization lag (§6 metrics)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - ts).total_seconds())


def _resolve_prompt(config: dict) -> str:
    inline = config.get("EVENT_SUMMARIZATION_PROMPT")
    if inline:
        return inline
    version = config.get("EVENT_SUMMARIZATION_PROMPT_VERSION") or os.environ.get("EVENT_SUMMARIZATION_PROMPT_VERSION")
    if version:
        try:
            return load_prompt(version)
        except FileNotFoundError as exc:
            LOGGER.warning("%s; falling back to the default prompt", exc)
    return DEFAULT_PROMPT


class SummaryDispatcher:
    def __init__(self, db, config: dict):
        self._db = db
        self.model = config.get("OPENAI_SUMMARY_MODEL", "gpt-5-mini")
        self.prompt = _resolve_prompt(config)
        self.min_chars = 0
        self._slots = BoundedSemaphore(1)
        self._summarizer: Summarizer | None = None
        self._executor: ThreadPoolExecutor | None = None
        self.enabled = False

        # Aggregate counters (§6 metrics). Mutated from pool threads, so guard with a lock.
        self._stats_lock = Lock()
        self._n_ok = 0
        self._n_failed = 0
        self._n_dropped = 0
        self._n_since_log = 0

        try:
            if not config.get("EVENT_SUMMARIZATION_ENABLED", False):
                raise ValueError("EVENT_SUMMARIZATION_ENABLED=false")
            self.min_chars = int(config.get("EVENT_SUMMARIZATION_MIN_CHARS", 0))
            max_concurrency = int(config.get("EVENT_SUMMARIZATION_MAX_CONCURRENCY", 4))
            max_backlog = int(config.get("EVENT_SUMMARIZATION_MAX_BACKLOG", 1000))
            self._slots = BoundedSemaphore(max_backlog)
            api_key = config.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY is missing")
            self._summarizer = Summarizer(api_key=api_key, base_url=config.get("OPENAI_BASE_URL"))
            self._executor = ThreadPoolExecutor(max_workers=max_concurrency, thread_name_prefix="event-summarizer")
        except Exception as exc:  # noqa: BLE001 - summarization setup must never break the embedding worker
            LOGGER.info("Event summarization disabled: %s", exc)
            return

        self.enabled = True
        LOGGER.info(
            "Event summarization enabled (model=%s, concurrency=%d, max_backlog=%d, min_chars=%d)",
            self.model,
            max_concurrency,
            max_backlog,
            self.min_chars,
        )

    def dispatch(self, run_id: UUID, severity: str, ts: datetime, message: str) -> None:
        if not self.enabled or self._executor is None or not message:
            return
        if len(message) < self.min_chars:
            return
        if not self._slots.acquire(blocking=False):
            self._bump("dropped")
            LOGGER.warning("Summarization backlog full; dropping run_id=%s ts=%s", run_id, ts)
            return
        try:
            self._executor.submit(self._summarize_and_store, run_id, severity, ts, message)
        except Exception as exc:  # noqa: BLE001 - dispatch must never disrupt the embedding path
            self._slots.release()
            LOGGER.warning("Could not dispatch summarization run_id=%s ts=%s: %s", run_id, ts, exc)

    def _summarize_and_store(self, run_id: UUID, severity: str, ts: datetime, message: str) -> None:
        try:
            result = self._summarizer.summarize(self.model, message, prompt=self.prompt)
            query = f"UPDATE {_SCT_EVENT_TABLE} SET summary = ? WHERE run_id = ? AND severity = ? AND ts = ?"
            # ScyllaConnection.execute swallows write failures and returns None; a null result
            # means the summary never persisted, so don't count/log it as a success.
            if self._db.execute(query, (result.summary, run_id, severity, ts)) is None:
                raise SummarizerError("summary DB write failed (execute returned None)")
            self._bump("ok")
            LOGGER.info(
                "Summarized run_id=%s severity=%s ts=%s: %d->%d chars, %d->%d tok (%d cached), %.0fms, lag=%.1fs",
                run_id,
                severity,
                ts,
                len(message),
                len(result.summary),
                result.prompt_tokens,
                result.completion_tokens,
                result.cached_tokens,
                result.latency_ms,
                _lag_seconds(ts),
            )
        except SummarizerError as exc:
            self._bump("failed")
            LOGGER.warning("Summarization failed run_id=%s ts=%s: %s", run_id, ts, exc)
        except Exception as exc:  # noqa: BLE001 - a task must never crash a pool thread
            self._bump("failed")
            LOGGER.error("Summarize/store error run_id=%s ts=%s: %s", run_id, ts, exc, exc_info=True)
        finally:
            self._slots.release()

    def _bump(self, kind: str) -> None:
        """Increment an aggregate counter and emit a rolling tally every _STATS_LOG_EVERY events."""
        with self._stats_lock:
            if kind == "ok":
                self._n_ok += 1
            elif kind == "failed":
                self._n_failed += 1
            elif kind == "dropped":
                self._n_dropped += 1
            self._n_since_log += 1
            due = self._n_since_log >= _STATS_LOG_EVERY
            if due:
                self._n_since_log = 0
                snapshot = (self._n_ok, self._n_failed, self._n_dropped)
        if due:
            self._log_stats(*snapshot)

    @staticmethod
    def _log_stats(ok: int, failed: int, dropped: int) -> None:
        LOGGER.info(
            "Summarization totals: %d ok, %d failed, %d dropped (backlog full)",
            ok,
            failed,
            dropped,
        )

    def shutdown(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=True, cancel_futures=True)
            with self._stats_lock:
                snapshot = (self._n_ok, self._n_failed, self._n_dropped)
            self._log_stats(*snapshot)
            LOGGER.info("Summary dispatcher shut down")
