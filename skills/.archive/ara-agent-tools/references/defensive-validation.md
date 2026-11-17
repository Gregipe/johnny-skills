# Defensive Validation Patterns

## 1. Text-Tools Cross-Check

### Problem
The LLM can describe actions in conversational text without generating matching tool calls. "Create deal + attach Ajay" in text → only `create_deal` in tool_calls → attachment silently never happens.

### Pattern
After tool extraction in the observe loop, scan the LLM's text for action keywords and verify matching tool calls exist. Mismatch → force regeneration.

### Implementation (observe loop, after `data_tools`/`read_tools` split)

```python
_tool_names = [tc["name"] for tc in tool_calls]
_text_lower = (text or "").lower()
_action_map = {
    "attach_to_deal": ["attach", "link", "connect", "set.*contact"],
    "create_deal": ["create deal", "new deal", "add deal"],
    "create_lead": ["create lead", "new lead", "add lead"],
    "send_whatsapp": ["send whatsapp", "message", "text"],
    "send_email": ["send email", "email"],
    "update_lead": ["update lead", "change lead", "edit lead"],
    "update_deal": ["update deal", "change deal", "edit deal"],
    "update_deal_stage": ["move deal", "change stage"],
    "update_lead_stage": ["move lead"],
    "set_reminder": ["remind", "reminder", "set reminder"],
    "create_action": ["create action", "add action", "schedule"],
    "trigger_cadence": ["start cadence", "start sequence", "outbound"],
}
_missing = []
for tool, patterns in _action_map.items():
    if tool not in _tool_names:
        for p in patterns:
            if re.search(p, _text_lower):
                _missing.append((tool, p))
                break
if _missing:
    _missing_descs = [f"{t} (text mentions '{p}')" for t, p in _missing]
    _fix_prompt = f"Your response mentions actions without corresponding tool calls: {', '.join(_missing_descs)}. Either add the missing tool calls or remove those actions from your text. Re-generate your response with all described actions backed by real tool calls."
    loop_messages.append({"role": "user", "content": _fix_prompt})
    continue  # skip this iteration, let LLM fix
```

### Key Details
- Must run on EVERY observe loop iteration, not just first pass
- `_action_map` must match all data-modifying tools in TOOL_SCHEMAS
- Add new tools to the map when they're created
- Regex patterns should be specific enough to avoid false matches (e.g., "send" without context matches too broadly)

## 2. Confirmation Flow — No Duplicate Text

### Problem
The LLM generates proposal text AND the system generates `_build_pending_description`. Both were concatenated, showing the same proposal twice: "➕ Add lead: X — shall I create it?\n\n➕ Add lead: X — shall I create it?"

### Fix
If `resp_clean` (LLM text with markers stripped) is non-empty, use it alone:
```python
if resp_clean:
    pending_text = resp_clean
elif pending_desc and pending_desc != "Pending confirmation":
    pending_text = pending_desc
else:
    pending_text = "I can help with that."
```

## 3. Confirmation Flow — Cancel Stale Siblings

### Problem
Duplicate confirmation messages created TWO pending ActionItems. When Greg confirmed one, the other stayed `awaiting_approval`. Next message matched the stale sibling instead of being processed as new.

### Fix
After executing a confirmation, cancel all other `awaiting_approval` pendings:
```python
_others = db.query(ActionItem).filter(
    ActionItem.tenant_id == tenant_id,
    ActionItem.execution_state == "awaiting_approval",
    ActionItem.id != _live.id,
).all()
for _o in _others:
    _o.execution_state = "cancelled"
    _o.status = "resolved"
    _o.outcome_state = "cancelled"
```

## 4. Failure Diagnosis — Show Errors + Escalate

### Problem
The diagnosis prompt said "Some tools failed: update_action. Can you fix?" but never showed the actual error. LLM retried 3x with same broken args.

### Fix
Include error messages and escalate repeated failures:
```python
err_msg = (f.error.message if f.error and f.error.message else "unknown error")[:200]
_fail_details.append(f"{f.tool}: {err_msg}")

# Same tool failing 2+ times → escalate
_repeat = [t for t, c in _same_tool_count.items() if c >= 2]
if _repeat:
    _fail_msg += f"{', '.join(_repeat)} failed {max(_same_tool_count.values())} times. STOP retrying. Tell Greg exactly what you need."
```

## 5. Duplicate Creation Prevention

### Problem
`create_deal` had no duplicate check. Voice notes could create the same deal multiple times.

### Fix
```python
existing = db.query(Deal).filter(
    Deal.tenant_id == tenant_id,
    Deal.org_name == org_name
).first()
if existing:
    return f"Deal '{org_name}' already exists (id={existing.id[:8]}, stage={existing.stage}). Use update_deal to modify it, or attach_to_deal to add contacts."
```

### Pattern
All `create_*` tools should check for existing records by unique fields (name, phone, email for leads; org_name for deals).
