# Over-Generation + All-or-Nothing Rejection Cascade (June 2026)

## Incident: Jimmie Tete WhatsApp + Shriram Finance Deal

**Date:** June 17, 2026
**Server:** Hetzner CX23 (46.224.132.99)
**Tenant:** 3e736242

### Timeline (UTC)

```
03:59:11  User: "Ok - send a whatsApp message to Jimmie Tete and tell him that i will send the infosec today itself."
03:59:11  Ava:  "Got it — 2 things: create the Shriram Finance deal AND fire off that WhatsApp to Jimmie."
          → CONFIRM-FLOW created-pending: id=3bb54770 tools=[create_deal(Shriram Finance), send_whatsapp(Jimmie Tete)]
03:59:48  User: "Ignore the shriram finance deal for now and just handle the whatsApp to Jimmie please."
03:59:48  → CONFIRM-FLOW verdict: reject for pending id=3bb54770
03:59:48  Ava:  "Okay, cancelled — I won't make that change."
          → ActionItem 3bb54770 execution_state = cancelled
```

### Root Cause 1: Pipeline-Injection Over-Generation

The system prompt injects the full pipeline into every turn:

```python
# server.py ~line 6431-6446
leads = db.query(Lead).filter(Lead.tenant_id == tenant_id, Lead.stage != "archived").all()
deals = db.query(Deal).filter(Deal.tenant_id == tenant_id).all()
lead_details = "\n".join([
    f"- {l.name} | {l.company} | Stage: {l.stage} | ..."
    for l in leads
])
```

At the time of the incident, the pipeline contained:
- **Deal:** Shriram Finance | stage: new | contact: Ajay Fageria

The LLM was asked to "send a WhatsApp to Jimmie" but also saw a "new" stage deal in the pipeline. Having just listed its deal-creation capability two messages earlier ("What skills do you have?"), it bundled the deal creation into the proposal.

### Root Cause 2: All-or-Nothing Confirmation Architecture

`_classify_confirmation` (server.py line 353) returns a single token: `confirm`, `reject`, or `unrelated`. The classifier prompt:

```
PROPOSAL: "💰 Create deal: Shriram Finance — shall I create it?; 💬 Send WhatsApp to Jimmie Tete — ..."
OWNER'S REPLY: "Ignore the shriram finance deal for now and just handle the whatsApp to Jimmie please."
```

"Ignore" mapped to the reject bucket → `reject` → entire ActionItem cancelled.

The reject handler at line 6416 sets `execution_state = "cancelled"` for the entire row — no mechanism to split multi-tool proposals.

## Fix 1: Single-Action Guard (`_guard_single_action`)

### Location
Inserted in the observe loop, between `_built_desc = _build_pending_description(data_tools)` and `_pending_row = _AIStore(...)`, at server.py ~line 5901.

### Code

```python
def _guard_single_action(user_msg, data_tools):
    """If user asked for ONE action but LLM proposed multiple, trim to matching tool only."""
    import re as _re_g
    if len(data_tools) <= 1:
        return data_tools
    _msg = (user_msg or "").lower().strip()
    _VERBS = {
        "send": ["send_whatsapp", "send_email", "send_whatsapp_to_owner"],
        "create": ["create_lead", "create_deal", "create_action_item"],
        "update": ["update_lead", "update_deal", "update_action"],
        "change": ["update_lead", "update_deal", "update_action"],
        "edit": ["update_lead", "update_deal", "update_action"],
        "set": ["set_reminder", "set_cron"],
        "schedule": ["set_reminder", "set_cron", "schedule_message", "schedule_email"],
        "remind": ["set_reminder"],
        "move": ["update_lead_stage", "update_deal_stage"],
        "cancel": ["cancel_scheduled"],
        "stop": ["cancel_scheduled"],
        "delete": ["cancel_scheduled"],
        "remove": ["cancel_scheduled"],
        "attach": ["attach_to_deal"],
        "trigger": ["trigger_cadence"],
        "start": ["trigger_cadence"],
        "escalate": ["escalate_to_human"],
    }
    _found = set()
    for _v in _VERBS:
        if _re_g.search(r"(?:^|[\s,.;:!?]+)" + _re_g.escape(_v) + r"(?:[\s,.;:!?]+|$)", _msg):
            _found.add(_v)
    if len(_found) != 1:
        return data_tools  # multiple verbs or none — don't trim
    _verb = _found.pop()
    _allowed = set(_VERBS.get(_verb, []))
    if not _allowed:
        return data_tools
    _matching = [tc for tc in data_tools if tc.get("name", tc.get("tool", "")) in _allowed]
    if not _matching or len(_matching) == len(data_tools):
        return data_tools
    import logging
    _gl = logging.getLogger("ara.confirm")
    _gl.info("SINGLE-ACTION-GUARD: trimmed %d->%d tools (verb=%s, kept=%s, dropped=%s)" % (
        len(data_tools), len(_matching), _verb,
        [tc.get("name", tc.get("tool", "")) for tc in _matching],
        [tc.get("name", tc.get("tool", "")) for tc in data_tools if tc not in _matching]))
    return _matching
```

### Call Site

```python
_built_desc = _build_pending_description(data_tools)
# ── Single-action guard: trim unsolicited extra tools ──
_data_tools_before = len(data_tools)
data_tools = _guard_single_action(user_msg, data_tools)
if len(data_tools) != _data_tools_before:
    _built_desc = _build_pending_description(data_tools)
_pending_row = _AIStore(...)
```

### When It Fires

| User message | Verbs found | Tools proposed | Result |
|---|---|---|---|
| "send a WhatsApp to Jimmie" | send | create_deal, send_whatsapp | Keeps send_whatsapp only |
| "create a deal and send a WhatsApp" | create, send | create_deal, send_whatsapp | Keeps both (2 verbs) |
| "update the lead" | update | update_lead, create_deal | Keeps update_lead only |
| "what's the pipeline?" | (none) | (any) | Keeps all (no verb found) |

## Fix 2: Partial Confirmation (`_split_partial_rejection`)

### Location
Inserted after `_classify_confirmation` function. Called from the `reject` handler at server.py ~line 6416.

### Code

```python
def _split_partial_rejection(user_msg, pending_tool_calls):
    """Parse 'ignore X, just do Y' and return (keep_tools, reject_tools)."""
    import re as _re_s
    if not pending_tool_calls or len(pending_tool_calls) <= 1:
        return None, None
    _msg = (user_msg or "").lower().strip()
    
    # Pattern 1: "ignore X", "skip X"
    _skip_entity = None
    for _pat in [
        r"ignore\s+(?:the\s+)?(.+?)(?:\s+(?:and|for|just|only|but|please|now)\s|$)",
        r"skip\s+(?:the\s+)?(.+?)(?:\s+(?:and|for|just|only|but|please|now)\s|$)",
    ]:
        _m = _re_s.search(_pat, _msg)
        if _m:
            _skip_entity = _m.group(1).strip().rstrip(".,;:!?")
            break
    
    # Pattern 2: "just do Y", "only Y", "but handle Y"
    _keep_entity = None
    for _pat in [
        r"(?:just|only)\s+(?:handle|do|send|create|make|fire)\s+(?:the\s+)?(.+?)(?:\s+(?:and|for|now|please)\s|$)",
        r"but\s+(?:handle|do|send|create|make|fire)\s+(?:the\s+)?(.+?)(?:\s+(?:and|for|now|please)\s|$)",
    ]:
        _m = _re_s.search(_pat, _msg)
        if _m:
            _keep_entity = _m.group(1).strip().rstrip(".,;:!?")
            break
    
    if not _skip_entity and not _keep_entity:
        return None, None
    
    def _tool_matches_entity(tc, entity):
        args = tc.get("args", {}) or {}
        _el = entity.lower()
        for _key in ("lead_name", "org_name", "deal_name", "name", "title", "message"):
            _val = str(args.get(_key, "")).lower()
            if _el in _val or _val in _el:
                return True
        return False
    
    keep, reject = [], []
    for tc in pending_tool_calls:
        if _skip_entity and _tool_matches_entity(tc, _skip_entity):
            reject.append(tc)
        elif _keep_entity and _tool_matches_entity(tc, _keep_entity):
            keep.append(tc)
        else:
            keep.append(tc)
    
    if not keep:
        return None, None  # everything rejected — fall through to normal reject
    
    import logging
    _sl = logging.getLogger("ara.confirm")
    _sl.info("PARTIAL-REJECT: keeping=%d tools, rejecting=%d tools (skip=%s, keep=%s)" % (
        len(keep), len(reject),
        [tc.get("name", tc.get("tool", "")) for tc in reject],
        [tc.get("name", tc.get("tool", "")) for tc in keep]))
    return keep, reject
```

### Modified Reject Handler

```python
elif _verdict == "reject":
    import json as _pj_reject
    _pending_calls_rej = []
    try:
        _pending_calls_rej = _pj_reject.loads(_live.pending_tool_calls or "[]")
    except Exception:
        _pending_calls_rej = []
    _keep, _reject_tools = _split_partial_rejection(user_msg, _pending_calls_rej)
    if _keep and len(_keep) > 0:
        # Partial rejection: execute kept tools, drop rejected ones
        _pending_results = []
        for _pc in _keep:
            _tn = _pc.get("tool", _pc.get("name", ""))
            _ta = _pc.get("args", {})
            _r = execute_tool(_tn, _ta, db, wa, tenant_id)
            _tr = _r if isinstance(_r, ToolResult) else from_legacy_string(_tn, _r)
            _pending_results.append(_tr)
        from render_results import render_results as _render_rej
        _resp_text = _render_rej(_pending_results, channel="whatsapp")
        _live.execution_state = "fired"
        _live.status = "resolved"
        _live.outcome_state = "resolved"
        _live.resolved_at = datetime.utcnow()
        # Cancel siblings
        _others_rej = db.query(ActionItem).filter(
            ActionItem.tenant_id == tenant_id,
            ActionItem.execution_state == "awaiting_approval",
            ActionItem.id != _live.id,
        ).all()
        for _o in _others_rej:
            _o.execution_state = "cancelled"
            _o.status = "resolved"
            _o.outcome_state = "cancelled"
        _tr_json_rej = _pj_reject.dumps([r.to_dict() if hasattr(r, "to_dict") else {"ok": False} for r in _pending_results])
        db.add(AgentChatMessage(tenant_id=tenant_id, role="user", content=user_msg, thread_id=thread_id))
        db.add(AgentChatMessage(tenant_id=tenant_id, role="assistant", content=_resp_text, thread_id=thread_id, tool_results=_tr_json_rej))
        db.commit()
        return {"response": _resp_text, "thread_id": thread_id, "tool_results": _tr_json_rej}
    # Full rejection — cancel everything (original behavior)
    _live.execution_state = "cancelled"
    ...
```

### When It Fires

| User reply | Pending tools | Keep | Reject |
|---|---|---|---|
| "Ignore the shriram finance deal, just handle the whatsApp" | create_deal(Shriram), send_whatsapp(Jimmie) | send_whatsapp | create_deal |
| "Skip the deal, send the message" | create_deal(X), send_whatsapp(Y) | send_whatsapp | create_deal |
| "No, cancel everything" | (any) | None → normal reject | — |
| "Yes, do it" | (any) | Not reached (verdict=confirm) | — |

### Edge Cases Handled

- **Single tool pending:** Returns `(None, None)` immediately — falls through to normal reject
- **No skip/keep pattern detected:** Returns `(None, None)` — falls through to normal reject
- **All tools match skip entity:** Returns `(None, None)` — falls through to normal reject
- **Entity matching is fuzzy:** `"shriram finance deal"` matches `org_name="Shriram Finance"` via `"shriram finance" in "shriram finance"` substring check
- **Unmatched tools default to keep:** If a tool doesn't match skip OR keep patterns, it's kept (user probably meant "do the other thing")

## Verification

After deploying both fixes, test with the exact scenario that failed:

1. Send a single-action request: "send a WhatsApp to Jimmie Tete"
2. Verify only ONE tool call in the pending ActionItem (no create_deal for pipeline items)
3. For a multi-tool proposal (intentional), reply: "ignore X, just do Y"
4. Verify only the kept tool executes, the rejected one is dropped
5. Check server logs for `SINGLE-ACTION-GUARD` and `PARTIAL-REJECT` messages
