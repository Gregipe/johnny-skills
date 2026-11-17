# Multi-Step Confirmation Execution (June 2026)

Architectural pattern for executing multi-tool pending proposals one step at a time with progress reporting.

## Architecture

When Ava proposes multiple tool calls in a single response (e.g., "Create PayTM deal + attach Vinay Bhoj"), the system:

1. Stores all tool calls as a JSON array in `ActionItem.pending_tool_calls`
2. Shows the user a confirmation prompt listing all proposed actions
3. On confirmation, executes only the FIRST tool
4. Updates the pending row: removes the executed tool, keeps the rest
5. Shows progress: "✅ Step 1/2: Created deal. ⏭ Next (2/2): Attach Vinay Bhoj — continue?"
6. On next confirmation, executes the next tool
7. Final step marks the pending as `fired`

## Code (in agent_chat confirmation path, `server.py`)

```python
if _verdict == "confirm":
    _pending_calls = json.loads(_live.pending_tool_calls or "[]")
    
    if len(_pending_calls) <= 1:
        # Single tool (or last in queue): execute and finalize
        for _pc in _pending_calls:
            _r = execute_tool(_pc.get("tool", ""), _pc.get("args", {}), db, wa, tenant_id)
        _resp_text = render_results(pending_results, channel="whatsapp")
        _live.execution_state = "fired"
        _live.status = "resolved"
        _live.resolved_at = datetime.utcnow()
    else:
        # Multi-step: execute ONE, keep rest queued
        _total = len(_pending_calls)
        _first = _pending_calls[0]
        _rest = _pending_calls[1:]
        
        _r = execute_tool(_first.get("tool", ""), _first.get("args", {}), db, wa, tenant_id)
        _step_done = _total - len(_rest)
        _step_result = _r.summary if _r and _r.summary else str(_r)[:120]
        
        _next_desc = _build_pending_description(_rest[:1]) if _rest else ""
        _next_line = f"\n\n⏭ Next ({_step_done + 1}/{_total}): {_next_desc}" if _next_desc else ""
        _resp_text = f"✅ Step {_step_done}/{_total}: {_step_result}{_next_line}"
        
        # Keep rest queued — do NOT mark as fired
        _live.pending_tool_calls = json.dumps(_rest)
        _live.description = f"[Step {_step_done}/{_total}] {_step_result}"
        _live.execution_state = "awaiting_approval"  # stays pending
```

## Prompt: Multi-Step Plan Description

The system prompt teaches Ava to describe the full plan before execution:

```
When Greg asks for multiple actions in one message, break it into a numbered plan:

1. Count and describe each action
2. Include ALL tool calls in your response — system executes one at a time
3. After each step, Greg sees the result and the system prompts to continue
4. If any step fails, system pauses and asks for clarification

Example flow:
  Ava: "Got it — 2 things: (1) create Shriram Finance deal, (2) attach Ajay as contact."
  Greg: "yes"
  System: "✅ Step 1/2: Created deal. ⏭ Next (2/2): Attach Ajay — continue?"
  Greg: "yes"
  System: "✅ Step 2/2: Attached Ajay Fageria to Shriram Finance. All done!"
```

## Structural Cross-Check

The observe loop scans LLM text for action keywords and verifies matching tool calls exist:

```python
_action_map = {
    "create_deal": ["create a deal", "create deal", "new deal for"],
    "attach_to_deal": ["attach", "attach.*as.*contact", "primary contact"],
    "create_lead": ["create a lead", "add.*contact", "new lead"],
    # ... more
}

_missing = []
for tool, patterns in _action_map.items():
    if tool not in tool_names:
        for p in patterns:
            if re.search(p, _text_lower):
                _missing.append((tool, p))
                break

if _missing:
    # Re-prompt LLM to add missing tool calls
    _fix_prompt = f"Your response mentions actions without tool calls: ..."
```

## Key Design Decisions

1. **Atomic execution**: Each tool executes in its own confirmation cycle. If step 2 fails, step 1 is already committed and safe.
2. **Queue preservation**: The `pending_tool_calls` JSON array shrinks as steps complete. The same ActionItem row tracks progress.
3. **Progress visibility**: Each step shows what was done AND what's next.
4. **Sibling cancellation**: When a multi-step pending executes, all OTHER `awaiting_approval` pendings are cancelled to prevent cross-contamination.
