# Ava System Pitfalls — 2026-06-16 Session

## lead_id doesn't exist on ActionItem

ActionItem has `ref_type` ('lead', 'deal', 'conversation') and `ref_id`, NOT `lead_id`.

**Correct pattern:**
```python
if a.ref_type == "lead" and a.ref_id:
    lead = db.query(Lead).filter(Lead.id == a.ref_id).first()
    if lead:
        lead_name = lead.name
```

**Locations that had this bug (all fixed):**
- `get_action_items` agent tool handler (~line 4680)
- Morning briefing `__morning_briefing__` generator (~line 8880)
- `/api/action-items` dashboard endpoint (~line 8045)

## save_memory vs add_skill — wrong target table

Two skill storage paths exist, and Ava's prompt historically pointed to the WRONG one:

| Tool | Category | Injected into agent_chat? | Searchable by search_memory? |
|------|----------|---------------------------|------------------------------|
| `save_memory` | "memory" | ✅ Yes (line ~6413) | ✅ Yes |
| `add_skill` | anything else | ❌ No (outreach only) | ❌ No |

**Fix:** System prompt "Learning the User" section must direct Ava to use `save_memory`/`search_memory`, not `add_skill`/`search_knowledge_base`. This was changed in June 16 session.

**Even after skills injection unification** (all categories now load into agent_chat context), `search_memory` still only searches category="memory" — so add_skill entries remain unfindable by the primary search tool.

## datetime comparison timezone mismatch

`utcnow()` from database.py may return timezone-aware datetime (varies by Python version). ActionItem.due_at is stored as naive UTC.

**Always use `datetime.utcnow()` (naive) for comparisons against DB columns.**

Failure signature: `TypeError: can't compare offset-naive and offset-aware datetimes`

## Multi-step confirmation missing _pending_results

When the confirmation flow has multiple pending tools:
```python
if len(_pending_calls) > 1:
    _first = _pending_calls[0]
    _rest = _pending_calls[1:]
    _r = execute_tool(...)
    _tr = ...
    _pending_results = [_tr]  # ← REQUIRED for _tr_json builder below
    _live.pending_tool_calls = json.dumps(_rest)
    _live.execution_state = "awaiting_approval"  # NOT "fired"
```

Without `_pending_results = [_tr]`, the downstream `if _pending_results:` check at line ~6306 skips tool result storage.

## Structural cross-check first_pass guard

The text-to-tools cross-check had `if _missing and not first_pass:` preventing it from running on the first LLM generation pass — exactly when mismatches occur.

**Fix:** `if _missing:` (remove `not first_pass` guard). The cross-check must validate every pass.

## Overdue computation pattern

Two API endpoints need overdue status:
- `/api/action-items` (line ~8016) — returns computed `status: "overdue"` when `due_at < now and status in ("open", "in_progress")`
- `/api/actions` (line ~2720) — same, comparing against `execution_state`/`outcome_state`

Both now include `"overdue"` in stats endpoint counts.
