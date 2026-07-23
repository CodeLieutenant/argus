Summarize this ScyllaDB test (SCT) ERROR/CRITICAL event into a short, readable triage summary.

This summary is the FIRST-PASS view for an engineer or an AI investigator. The full original event is always available on demand, so do NOT reproduce it verbatim — compress aggressively. A reader who needs the raw stack trace, full log lines, or exact offsets will open the original; your job is to let them decide whether they need to.

Produce a compact Markdown summary with:
- a one-line **headline**: the failure/event type, the key value(s), the node and shard, and the severity in plain terms (e.g. non-fatal warning vs fatal error)
- **Root cause**: the most likely cause in one or two lines, in plain engineering language — transform the stack trace into meaning (the operation and subsystem involved), do not list raw frames or hex addresses
- **Call chain**: the meaningful sequence of operations, as decoded symbols/subsystems where the event names them; omit library glue and raw addresses
- **Trigger**: what set it off, if the event supports an answer
- **Event ID** and **timestamp**

Faithfulness rules (this is what keeps the summary trustworthy):
- Base the root cause and call chain ONLY on what the event actually evidences — the error message, named libraries/symbols, offsets, and log text present. Do NOT invent specific function names, subsystems, or causes the event does not support.
- If the cause or call chain is not determinable from the event, say so briefly (e.g. "root cause not evident from the backtrace") rather than guessing. A cautious, correct summary beats a confident, wrong one.
- Never contradict a value in the event; copy exact identifiers (event id, node, numbers) rather than paraphrasing them.

Aim for the fewest tokens that still let a triager understand what failed and decide whether to open the original. Output concise Markdown, no preamble.
