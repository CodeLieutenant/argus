"""JSONL replay log for Argus client API calls.

Every mutating (POST) request is recorded as a single JSONL line so that,
when Argus is unavailable, the recorded calls can be replayed against the
server once it recovers. See ``docs/plans/request_replay.md`` for the full
design.

Each request thread runs the HTTP call, populates the outcome, and writes one
complete record to disk. Writes are synchronous, serialized by a single lock
-- there is no background thread or queue, so a failing write can never grow
unbounded memory and a slow disk just adds latency to the calling request
instead of losing data silently. A write failure is always logged and
swallowed rather than raised: logging must never be the reason the real
Argus API call doesn't happen, and never the reason a caller's cleanup path
raises.

A crash (SIGKILL) mid-call can still lose the record for whatever request
was in flight at that moment -- that's accepted rather than worked around:
the process is gone either way, so one lost record is the least of anyone's
problems.
"""
from __future__ import annotations

import atexit
import functools
import itertools
import json
import logging
import os
import re
import threading
import time
import weakref
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any, Iterator

_instance_counter = itertools.count()

LOGGER = logging.getLogger(__name__)

# Allow only characters that are unambiguously safe inside a filename.
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9_-]")


def _sanitize_for_filename(value: str) -> str:
    # Strip any path-significant characters (slashes, dots) so a hostile run-id
    # cannot escape ``log_dir``. Dots are dropped entirely rather than mapped
    # to ``_`` so ``..`` cannot survive the substitution.
    return _UNSAFE_FILENAME_CHARS.sub("_", value) or "unknown"


def _now_ns() -> int:
    return time.time_ns()


def classify_response(response: Any) -> tuple[bool, str | None]:
    """Classify a ``requests.Response`` as success/failure for the replay log.

    Only a response with ``response.ok`` true (status < 400) and a JSON body
    with ``status == "ok"`` counts as success. A non-2xx/3xx status, a
    non-JSON body (auth proxy, gateway error), or ``{"status": "error", ...}``
    is a failure.
    """
    if not response.ok:
        return False, f"HTTP {response.status_code}"
    try:
        payload = response.json()
    except ValueError:
        return False, f"HTTP {response.status_code} non-JSON response"
    if payload.get("status") == "ok":
        return True, None
    return False, f"HTTP {response.status_code} status={payload.get('status')!r}"


class ReplayLogOnlyResponse:
    """Stub :class:`requests.Response` returned in replay-log-only mode.

    Satisfies :meth:`ArgusAPIClient.check_response` so callers continue
    without error. The real request is preserved in the replay log for later
    replay.
    """

    status_code = 200
    ok = True

    def __init__(self, endpoint: str) -> None:
        self.url = f"replay-log-only:{endpoint}"
        self.request = None
        self.text = '{"status":"ok","response":{}}'
        self.content = self.text.encode("utf-8")

    def json(self) -> dict:
        return {"status": "ok", "response": {}}

    def raise_for_status(self) -> None:
        return None


class ReplayLog:
    """Append-only JSONL journal of Argus API calls for one client instance.

    Writes are synchronous and serialized by a single lock -- the calling
    thread pays for its own write, there is no background thread, queue, or
    unbounded buffer that could grow if the disk is unwritable.

    If the log file cannot be opened (bad ``log_dir``, permission error, full
    disk), the instance still constructs successfully and simply drops every
    record -- a broken replay log must never prevent the real Argus client
    from being created or from making its real HTTP calls.
    """

    def __init__(
        self,
        *,
        log_dir: str | Path,
        run_id: str | None = None,
        test_type: str | None = None,
    ) -> None:
        safe_run_id = _sanitize_for_filename(run_id or "unknown")
        log_dir_path = Path(log_dir)
        # Nanosecond clock + pid + process-wide counter guarantees uniqueness
        # across parallel processes and back-to-back instantiation, even when
        # the system clock has coarser-than-nanosecond resolution.
        suffix = f"{_now_ns()}_{os.getpid()}_{next(_instance_counter)}"
        self._path: Path = log_dir_path / f"argus_replay_log_{safe_run_id}_{suffix}.jsonl"
        self._test_type: str = test_type or "unknown"
        self._lock = threading.Lock()
        self._closed = False
        self._file: IO[str] | None = None
        try:
            log_dir_path.mkdir(parents=True, exist_ok=True)
            self._file = open(self._path, "a", encoding="utf-8")
        except OSError:
            LOGGER.exception(
                "argus replay log: could not open %s for writing; replay log disabled", self._path,
            )
        self._atexit_ref: weakref.ReferenceType[ReplayLog] = weakref.ref(self)
        self._atexit_callback = functools.partial(self._atexit_close, self._atexit_ref)
        atexit.register(self._atexit_callback)

    @staticmethod
    def _atexit_close(log_ref: "weakref.ReferenceType[ReplayLog]") -> None:
        log = log_ref()
        if log is not None:
            log.close()

    @property
    def path(self) -> Path:
        return self._path

    def __enter__(self) -> "ReplayLog":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @contextmanager
    def record(
        self,
        method: str,
        endpoint: str,
        location_params: dict | None,
        params: dict | None,
        body: dict | None,
    ) -> Iterator[dict]:
        """Yield a mutable dict for the caller to populate with the outcome.

        The caller runs the HTTP call inside the ``with`` block and sets
        ``rec["success"]``/``rec["error"]`` from the response. If the block
        raises, ``success`` is set to ``False`` and ``error`` captures the
        exception before it propagates. Either way, the record is written to
        disk exactly once, when the block exits.
        """
        rec: dict = {
            "ts": _now_ns() // 1_000_000,
            "method": method,
            "endpoint": endpoint,
            "location_params": location_params,
            "params": params,
            "body": body,
            "test_type": self._test_type,
            "success": False,
            "error": None,
        }
        try:
            yield rec
        except Exception as exc:
            rec["success"] = False
            rec["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self._write(rec)

    def _write(self, rec: dict) -> None:
        try:
            # Omit ``error`` when there is no error to keep records compact.
            if rec.get("error") is None:
                rec.pop("error", None)
            # Compact separators (no spaces) -- ~10-15% smaller than default.
            line = json.dumps(rec, default=str, separators=(",", ":"), ensure_ascii=False) + "\n"
        except Exception:
            # Serialization must never take down the caller's request; drop
            # this one record rather than raise out of record().
            LOGGER.exception("argus replay log: failed to serialize record; record dropped")
            return
        with self._lock:
            if self._file is None:
                # Already logged loudly once, in __init__, when the file
                # failed to open -- avoid re-warning on every record.
                LOGGER.debug(
                    "argus replay log: log unavailable; dropping record for %s %s",
                    rec.get("method"), rec.get("endpoint"),
                )
                return
            if self._closed:
                LOGGER.warning(
                    "argus replay log: log already closed; dropping record for %s %s",
                    rec.get("method"), rec.get("endpoint"),
                )
                return
            try:
                # write + flush only: fsync/fdatasync was measured (100
                # concurrent threads) to add no durability benefit here and
                # cost real latency on every request -- see PR discussion.
                self._file.write(line)
                self._file.flush()
            except Exception:
                # A write failure must never propagate into the caller's
                # request handling; the record for this one call is lost.
                LOGGER.exception("argus replay log: write failed; record dropped")

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._file is not None:
                try:
                    self._file.close()
                except OSError:
                    LOGGER.exception("argus replay log: error closing %s", self._path)
        atexit.unregister(self._atexit_callback)
