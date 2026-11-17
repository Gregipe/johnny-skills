# Multi-Step Confirmation Execution (Batch Mode, June 2026)

## Design Decision (June 18, 2026): Batch Execution

The multi-step "confirm each tool individually" pattern was **removed** in favor of batch execution. The old pattern:
- User says "yes" → one tool executes → "⏭ Next (2/9)..." → user says "yes" → next tool...
- 9 actions required 9 confirmations — tedious UX
- Numbering was broken: showed "Step 1/9, Step 1/8, Step 1/7..." because `_total` kept shrinking

**New pattern:** One confirmation executes ALL pending tools. The user sees a single proposal ("Create 9 actions — shall I go ahead?"), says "yes" once, and all tools execute. Results are summarized via `render_results()`.

The `_split_partial_rejection` path (reject branch) is unaffected — the user can still say "ignore X, just do Y" to selectively execute.

## Implementation (confirmation confirm path, ~line 6493)

```python
# ── Execute all pending tools in one go ──
_total = len(_pending_calls)
_pending_results = []
_cf_log.info("CONFIRM-FLOW executing all %d tool(s)" % _total)
for _i, _pc in enumerate(_pending_calls):
    _tn = _pc.get("tool", "")
    _cf_log.info("CONFIRM-FLOW exec %d/%d: tool=%s" % (_i + 1, _total, _tn))
    try:
        _r = execute_tool(_tn, _pc.get("args", {}), db, wa, tenant_id)
        _tr = _r if isinstance(_r, ToolResult) else from_legacy_string(_tn, _r)
    except Exception as _exc:
        _tr = ToolResult(ok=False, summary="Error: %s" % str(_exc)[:120])
        _cf_log.error("CONFIRM-FLOW exec FAILED %d/%d: %s" % (_i + 1, _total, str(_exc)[:200]))
    _pending_results.append(_tr)
_resp_text = render_results(_pending_results, channel="whatsapp")
_live.execution_state = "fired"
_live.status = "resolved"
_live.outcome_state = "resolved"
_live.resolved_at = datetime.utcnow()
```

### Key details
- Each tool is wrapped in try/except — failure of one tool does not prevent subsequent tools from executing
- `_pending_results` accumulates all results for the `render_results()` summary
- After all tools execute, the row is marked `fired/resolved/resolved` (no more awaiting_approval)
- The `_total` variable and `_i + 1` provide accurate progress reporting in logs

## Removed: Old Multi-Step Pattern (pre June 18, 2026)

```python
if len(_pending_calls) <= 1:
    # Single tool (or last in queue): execute and finalize
    _pending_results = []
    for _pc in _pending_calls:
        _r = execute_tool(_pc["tool"], _pc["args"], db, wa, tenant_id)
        _tr = _r if isinstance(_r, ToolResult) else from_legacy_string(_pc["tool"], _r)
        _pending_results.append(_tr)
    _resp_text = render_results(_pending_results, channel="whatsapp")
    _live.execution_state = "fired"
    _live.status = "resolved"
else:
    # Multi-step: execute ONE tool, keep rest queued
    _total = len(_pending_calls)
    _first = _pending_calls[0]
    _rest = _pending_calls[1:]
    _r = execute_tool(_first["tool"], _first["args"], db, wa, tenant_id)
    _tr = _r if isinstance(_r, ToolResult) else from_legacy_string(_first["tool"], _r)
    _pending_results = [_tr]
    _step_done = _total - len(_rest)
    _step_result = _tr.summary if _tr and _tr.summary else str(_tr)[:120] if _tr else "done"
    _next_desc = _build_pending_description(_rest[:1]) if _rest else ""
    _next_line = f"\n\n⏭ Next ({_step_done + 1}/{_total}): {_next_desc}" if _next_desc else ""
    _resp_text = f"✅ Step {_step_done}/{_total}: {_step_result}{_next_line}"
    # Update pending: keep rest for next confirmation
    _live.pending_tool_calls = json.dumps(_rest)
    _live.description = f"[Step {_step_done}/{_total}] {_step_result}"
    _live.execution_state = "awaiting_approval"  # keep alive
```

## User Flow

```
Ava: "Got it — 2 things: (1) create PayTM deal, (2) attach Vinay Bhoj. Shall I start?"
Greg: "yes"
System: "✅ Step 1/2: Created deal PayTM: stage new
         ⏭ Next (2/2): 🔗 Attach Vinay Bhoj to deal PayTM — continue?"
Greg: "yes"
System: "✅ Step 2/2: Attached Vinay Bhoj to PayTM. All done!"
```

## System Prompt Addition

```
When Greg asks for multiple actions, break it into a numbered plan:
1. Describe all steps: "Got it — 3 things: (1) X, (2) Y, (3) Z."
2. Include ALL tool calls. The system executes one at a time with progress.
3. If any step fails, the system pauses and asks Greg.

Example: Ava → "2 things: (1) create deal, (2) attach contact. Shall I start?"
```

## Key Details
- `_pending_results` must be set even in multi-step path (for `_tr_json` below) — `_pending_results = [_tr]`
- After last step: `_live.execution_state = "fired"` (normal path by `len(_pending_calls) <= 1`)
- The `_build_pending_description` function needs a case for every tool type (was missing `attach_to_deal`)
