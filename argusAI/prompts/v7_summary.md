Summarize this ScyllaDB test (SCT) ERROR/CRITICAL event into a short, readable triage summary.

This is the FIRST-PASS view for an engineer or AI investigator. The full original event is always available on demand, so do NOT reproduce it verbatim — compress hard. Your job is to let the reader understand what failed and decide whether to open the original.

Adapt the shape to the event:

- If the event is SHORT (a line or two, no real stack trace): output a single headline line — failure/event type, key value(s), node/shard, and the exact error text — and stop. Do NOT add Root cause / Call chain / Trigger sections; there is nothing to decode, and inventing them is worse than omitting them.

- If the event carries a STACK TRACE or is long: output compact Markdown with
  - **Headline**: failure/event type, key value(s), node/shard, severity as literally stated
  - **Root cause**: one or two lines, only if the trace/message actually shows it — name the operation and subsystem from the decoded symbols present in the trace
  - **Call chain**: the meaningful decoded frames the trace names (skip hex addresses and library glue)
  - **Event ID** and **timestamp**

Faithfulness rules (non-negotiable — a wrong summary is worse than a terse one):
- State severity (non-fatal / fatal) ONLY if the event text says so. Do not infer it.
- Do NOT guess a trigger, root cause, or call chain that the event does not evidence. Only decode symbols and frames that literally appear in the trace. If the cause isn't determinable, write "root cause not evident from the event" — never speculate.
- Copy exact identifiers (event id, node, numbers, error strings) rather than paraphrasing; never contradict a value in the event.
- No hedging prose, no "may/might/likely" speculation about unstated behavior.

Aim for the fewest tokens that still convey what failed. Output concise Markdown (or a single line for short events), no preamble.
