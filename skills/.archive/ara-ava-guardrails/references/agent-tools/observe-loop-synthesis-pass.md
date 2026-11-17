# Observe Loop — Described-but-Uncalled Write Problem & Synthesis Pass

## The Problem

When an LLM agent calls tools in a loop, the model produces **text AND tool_calls in the same inference**. These two outputs are decoupled — the text can describe "Here's the WhatsApp I'll send" while `send_whatsapp` is absent from tool_calls. Nothing at the execution layer cross-checks them.

On multi-step commands ("update X AND send Y"), the model narrates Step 2 in prose while only calling Step 1's tools. The response claims both actions are done, but Step 2 never executed. This is a **false claim** — user sees "WhatsApp sent" but no message was delivered.

## Two-Layer Defense (commits 4814e60 + a77e6d8)

### Layer 1: Empty-tool_calls Retry (4814e60)
When the loop hits an empty `tool_calls` array, instead of breaking unconditionally, check if the text describes a write:

```
Case 1: No write described → break (genuine answer)
Case 2: Write asserted without tool call → one retry (short nudge)
Case 3: Proposal ("shall I?") → break (confirm flow handles)
Case 4: Retry exhausted → honest downgrade ("drafted, not sent")
```

The nudge: "You described sending something but issued no tool call. Either call it now or phrase as a question."

Key: assertion check runs BEFORE proposal check so "Done. Updated. Shall I send?" retries rather than breaking on the question mark.

**Limitation:** Only catches empty tool_calls. When the model has SOME tools (update_action) but not ALL (missing send_whatsapp), Layer 1 can't detect the gap.

### Layer 2: Tool-Free Synthesis Pass (a77e6d8)
After the observe loop terminates and at least one write tool executed, make a **tool-free** LLM call that composes the response from actual results:

```python
_synth_instruction = (
    "Compose the reply to the user based only on the tool results above. "
    "State what was actually done, reading from the results — never describe "
    "an action as done unless a result confirms it. If the reasoning trace "
    "indicates an action the user wanted that has NO corresponding result, "
    "do not claim it happened — instead offer it as a next step."
)
_synth_out = _ie.call_llm(loop_messages + [_synth_msg], model="...")
```

The synthesis model receives:
- All executed tool results (from loop_messages)
- The reasoning trace (inline assistant texts from each step)
- Instruction to compare intent vs outcome and offer, not claim

The synthesis call has **zero tools** — structurally cannot fabricate a result. If the model described sending a WhatsApp but no send result exists, the synthesis offers "Want me to send that now?"

**Read-only/status/smalltalk turns skip synthesis** — no extra call when writes weren't executed.

## Detection: Model Reasoning, Not Pattern Match

The gap detection is done by the synthesis model reasoning over the trace + results, NOT by code scanning text for verbs. This is deliberate — pattern-based detection expires the moment the model rephrases ("send a WhatsApp" vs "shoot him a message" vs "drop him a line").

## Gate Tests

1. **Multi-step 5×**: "update deadline AND send WhatsApp" → either both tools fire OR response offers the send. NEVER claims it sent when send_whatsapp absent.
2. **Single write**: "update deadline" → truthful narration, no invented second action.
3. **Read-only untouched**: "what's overdue?" → no synthesis pass, inline response as before.
4. **Proposal clean**: "Shall I send?" → breaks to confirm flow, no spurious send.
5. **Rephrasing resilience**: "shoot him a message" → if tool isn't called, still offers (not claims).

## Within-Turn Read Cache (per-turn dedup)

A `_read_cache` dict keyed on `(tool_name, json.dumps(args, sort_keys=True))` prevents duplicate read tool calls within a single turn. Populated on every read execution, checked before each read. Read-only tools only — never caches writes.

Cache scope: within-turn only. The data can't change between step 1 and step 4 of the same turn in a way that matters. Different args = different cache key = correctly uncached.

## Pitfalls

- **call_llm returns string, not dict**: `induction_engine.call_llm()` returns a plain string — not `{"text": "..."}`. Check `isinstance(resp, str)` before calling `.get()`.
- **Shell escaping with heredocs**: When running Python via SSH heredocs (`ssh ... "python3 << 'PYEOF'"`), escaping regex patterns and quotes becomes combinatorially broken. Always write Python to a temp file and SCP it instead.
- **File verification**: After patching `server.py` on a remote server, purge `.pyc` caches (`find . -name '__pycache__' -type d -exec rm -rf {} +`) and restart. Python may serve stale bytecode.
- **Synthesis latency**: The extra LLM call adds ~2-4s per write turn. Use the fast model (flash) for synthesis since it's summarization, not reasoning.
