# Described-But-Uncalled Write Retry

## Problem

In multi-step commands ("update X AND send Y"), the model sometimes describes the second action in prose ("Here's the WhatsApp I'll send") without including the corresponding tool in `tool_calls`. The observe loop's empty-tool_calls branch breaks unconditionally, accepting the prose as the final answer. The user sees "WhatsApp sent" language but no message was delivered.

## Root Cause

Text generation and tool calling are decoupled surfaces. The model can compose "Here's the WhatsApp I'll send to Amardeep: > message..." in prose without having `send_whatsapp` in its `tool_calls` array. Nothing at the execution layer forces them to agree.

## Fix: Four-Case Exit in `_run_observe_loop`

In `server.py`, at the empty-tool_calls branch (~line 5837), replace the unconditional `break` with:

```
Case 1: text doesn't describe a write → break (genuine answer, unchanged)
Case 2: text asserts a write as done, no tool call, retry_used=False 
        → one retry (inject short nudge, continue)
Case 3: text is a proposal ("shall I?", ends with ?, [ACTION: ASK]) 
        → break (confirm flow handles it)
Case 4: retry_used=True and text still asserts → honest downgrade 
        ("drafted, not sent") and break
```

**Critical ordering: Case 2 MUST run before Case 3.** A response like "Done. Updated. Shall I send?" should trigger the retry (case 2), not break as a proposal (case 3).

## Write Detection Regex

```
_write_verbs = r"\b(send|sent|create|created|update|updated|schedule|scheduled|move|moved|delete|deleted|attach|set|change)\b"
```
Must include past-tense forms — "sent" ≠ "send" for regex matching.

## Assertion Detection Regex

```
_asserts_done = r"(here.s the|i've|i am|i'm |now |let me |just |done|updated|sent|scheduled|moved|draft the|✅|✔)"
```

## Proposal Detection

```
_is_proposal = r"(shall i|want me to|should i|i'll\s.*if you|let me know if|would you like)"
+ text.rstrip().endswith("?")
+ "[ACTION: ASK]" in text
```

## Honest Downgrade

On second failure (retry already used), replace false-completion language:
- Replace "sent", "done", "updated", "created", "scheduled", "fired" with "drafted"
- Strip checkmark unicode (✅, ✔)
- Append "(drafted, not sent — want me to?)" if no honest language found

## Variables

- `retry_used = False` — initialized at top of `_run_observe_loop`
- `_mock_responses` — optional parameter for forced-failure testing (injects mock LLM responses)
- MAX_TOOL_STEPS should be at least 10 to accommodate retry + tool execution

## Testing

Mock testing via `_mock_responses` parameter:
```python
mock1 = {"text": "Updated. Here's the WhatsApp I'll send: ...", "tool_calls": [], ...}
mock2 = {"text": "I've sent the WhatsApp. All done!", "tool_calls": [], ...}
_run_observe_loop(..., _mock_responses=[mock1, mock2])
```

## Known Limitation

The retry only fires when `tool_calls` is entirely empty. When the model includes tools for action 1 AND describes action 2 in prose in the same turn, this is undetectable. This is the pre-existing two-decoupled-surfaces gap — text and tool_calls don't agree, and nothing at the execution layer forces them to. Single-action commands work correctly; only "do X AND send Y" triggers it.
