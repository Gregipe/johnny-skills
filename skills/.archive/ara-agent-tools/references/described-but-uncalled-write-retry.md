# Described-but-Uncalled Write Retry (June 17, 2026)

**Problem:** In multi-step commands ("update X and send Y a WhatsApp"), the model would
compose the update as a tool call but describe the send in prose ("Here's the WhatsApp I'll
send — > Hi Amardeep...") without issuing `send_whatsapp`. The observe loop broke on empty
`tool_calls`, treating the prose as the terminal response. The send silently vanished.

This is the two-decoupled-surfaces problem: text and tool_calls come from the same LLM
response but nothing forces them to agree. A write described in prose without a corresponding
tool call looks done but never happened.

## The Fix: Four-Case Exit Branch

In `_run_observe_loop`, at the empty-tool_calls branch (~line 5837):

### Case 1: Text doesn't describe a write → break (unchanged)
The model produced a genuine answer or conversation. No action verbs detected.
Regex: `\b(send|create|update|schedule|move|delete|attach|set|change)\b`
Behavior: `final_text = text; break`

### Case 2: Text asserts a write as done with no tool call → ONE retry
The model wrote language like "✅ Updated" or "Here's the WhatsApp I'll send" with
present/past-tense assertion language and no tool call.
Regex: `(here.s the|i've|i am|i'm |now |let me |just |done|updated|sent|scheduled|moved|draft the)`

Behavior: Inject a single short user nudge into `loop_messages`:
```
"You described sending something but issued no tool call, so it did not happen.
The prior action's result is above. Either call the tool now, or if you need
confirmation first, phrase it as a question."
```
Then `continue` — the model gets exactly one more turn.

**Critical rule:** Case 2 MUST run BEFORE the proposal check (Case 3). Text like
"✅ Updated. Shall I send it?" ends with "?" (proposal) but also asserts a done
action — the retry must fire, not the proposal break. The reorder from the original
implementation was the key fix (commit 4814e60).

### Case 3: Text describes a write as a proposal → break (confirm flow)
"Shall I send Rajesh a follow-up?", "want me to update?", ends with "?", or
contains `[ACTION: ASK]`.
Behavior: `final_text = text; break` — the confirmation flow handles it.

### Case 4: Retry exhausted → honest downgrade
If `retry_used` is already True (Case 2 already fired once) and the model STILL
describes a write without calling the tool, downgrade the response:
- Strip ✅/✔ symbols
- Replace "done/sent/updated/created/scheduled/fired" with "drafted"
- Append "(drafted, not sent — want me to?)" if not already phrased honestly
Behavior: `final_text = downgraded; break`

## Key Design Constraints

1. **One retry maximum.** The flag `retry_used` prevents looping. This is different
   from the deleted `_claims_action_without_call` guard which looped.
2. **The nudge is short.** It must not displace prior context — a single sentence,
   appended once.
3. **The retry message is injected as a user message** (not a system prompt nudge),
   so it carries conversational weight but doesn't contaminate the system prompt.
4. **All prior tool results are already in `loop_messages`** — the retry nudge
   goes at the end, so the model composes its next response against completed state.

## Pitfalls Discovered During Implementation

- **"let me draft" wasn't caught by the initial assertion regex.** Added "let me" and
  "draft the" to the assertion pattern.
- **"Both done" wasn't caught as describing a write** because it lacks a write verb.
  This is correct — "Both done" is a summary, not an assertion of a specific
  uncalled write. Case 1 handles it correctly.
- **Case order matters.** Original implementation had proposal check before
  assertion check. Text like "✅ Updated. What do you want me to send?" triggered
  the proposal break (ends with "?") before the assertion retry could fire.
  Reordered: assertion check first.

## Location in Code

`_run_observe_loop` in `server.py`, the empty-tool_calls branch (~line 5837).
Flag initialized as `retry_used = False` alongside other loop variables.
Commit: 4814e60.

## Test Verification

- `send_whatsapp` appears in tool list for multi-step commands ✓
- Proposal ("Shall I send?") breaks cleanly ✓
- Exhausted retry produces honest downgraded language ✓
- Status questions break immediately (unchanged) ✓
