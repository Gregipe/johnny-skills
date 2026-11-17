# Tool Boundary Patterns (June 2026)

## 1. Timezone Boundary: LLM→IST, Server→UTC

**Rule**: LLM thinks and communicates in the tenant's timezone (IST). Server stores in UTC. Auto-convert at the edges — never make the LLM do timezone math.

**Helpers** (added at module level before `execute_tool`):
```python
from datetime import timedelta as _IST_TD
IST_OFFSET = _IST_TD(hours=5, minutes=30)

def _parse_ist_to_utc(dt_str):
    """Parse IST datetime string (from LLM) → UTC datetime (for DB)."""
    dt = datetime.fromisoformat(dt_str.replace(' ', 'T'))
    if len(dt_str) <= 10:  # date-only — caller applies default
        return dt
    return dt - IST_OFFSET

def _format_utc_as_ist(dt_val):
    """Format UTC datetime → IST string for display."""
    if dt_val is None:
        return "none"
    ist_dt = dt_val + IST_OFFSET
    return ist_dt.strftime('%b %d %I:%M %p IST')
```

**Every tool handler accepting a time** must convert IST→UTC:
- `create_action`: `_due = _due - IST_OFFSET`
- `update_action`: `action.due_at = _dt.fromisoformat(raw.replace(' ', 'T')) - IST_OFFSET`
- `create_action_item`: `due = due - IST_OFFSET` (when has time component)

**Every tool displaying a time** must convert UTC→IST:
- `get_action_items`: `due: {_format_utc_as_ist(a.due_at)}`

**System prompt**: Single line replaces 9-line conversion table:
```
Current date/time: {datetime} ({timezone}).
⏱ All times you see and pass to tools are in IST.
   The server handles UTC conversion automatically.
   You never need to convert timezones — just use IST everywhere.
```

**Date-only default**: When the LLM passes date-only (e.g. "2026-06-16"), default to 6 PM IST (close of business), then convert to UTC:
```python
if len(_due_raw) <= 10:
    _due = datetime.fromisoformat(_due_raw).replace(hour=18, minute=0, second=0)
_due = _due - IST_OFFSET
```

## 2. `_build_pending_description` — Must Cover Every Data-Modifying Tool

**Problem**: `_build_pending_description()` (line 5930) has an explicit `if/elif` chain for each tool name. Missing tool entries cause combined proposals to show only partial actions. Example: voice note says "Create deal + attach Ajay" → only "💰 Create deal" appears in pending description because `attach_to_deal` had no entry.

**Rule**: When adding a new data-modifying tool:
1. Add handler in `execute_tool()`
2. Add schema entry in `AGENT_TOOL_SCHEMA`
3. **Add case in `_build_pending_description()`** — format: `{emoji} {verb}: {details} — shall I ___?`
4. If step 3 is skipped, multi-tool confirmations will silently drop actions

**Current coverage** (as of 2026-06-16):
```
set_reminder     ✅    send_whatsapp    ✅    update_lead_stage   ✅
set_cron         ✅    send_email       ✅    update_deal_stage   ✅
create_lead      ✅    update_lead      ✅    create_deal         ✅
attach_to_deal   ✅    trigger_cadence  ✅    create_action       ✅
escalate_to_human ✅   cancel_scheduled ✅
```

## 3. `get_action_items` Must Return Action IDs

**Problem**: Without action IDs in the output, the LLM cannot call `update_action(action_id=...)`. It resorts to `query_database` with hallucinated SQL column names (e.g., `lead_name` which doesn't exist in `action_items`).

**Fix**: Include `[id={a.id[:8]}]` in each action item line:
```python
result.append(f"  • [{a.status}] {a.title} ({a.action_type}) -- {created} [id={a.id[:8]}]")
```

This enables the clean flow: `get_action_items` → see ID → `update_action(action_id="0e494111", due_at="...")`.

## 4. `create_deal` Must Check for Duplicate `org_name`

**Problem**: Without a duplicate check, the LLM creates a second deal with the same company name. Two "Shriram Finance" deals exist in the DB, one with a contact and one without.

**Fix**:
```python
existing = db.query(Deal).filter(
    Deal.tenant_id == tenant_id,
    Deal.org_name == org_name
).first()
if existing:
    return f"Deal '{org_name}' already exists (id={existing.id[:8]}, stage={existing.stage}). Use update_deal to modify it, or attach_to_deal to add contacts."
```

## 5. `update_deal` Tool Description Must List All Updatable Fields

**Problem**: Tool description only mentioned `stage` and `expected_value`. LLM didn't know it could set `lead_id` (primary contact). Greg couldn't attach a contact person from the deal screen.

**Fix**: Expand description to show all commonly used fields:
```
Args: {"deal_name": "...", "fields": {"stage": "...", "expected_value": 500000,
       "lead_id": "abc123", "contact_name": "...", "value_notes": "..."}}
To attach a lead as primary contact, set lead_id to the lead's ID.
```

Also: auto-sync contact details when `lead_id` is set — query the lead and populate `contact_name`, `contact_email`, `contact_phone`.
