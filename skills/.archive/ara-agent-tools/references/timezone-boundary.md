# IST/UTC Timezone Boundary

## Problem
Ava was given a 9-line IST→UTC conversion table in her system prompt. She got conversions wrong ~50% of the time. Times would silently shift by 5.5 hours: 7 PM IST stored as 7 PM UTC (= 12:30 AM IST next day).

## Pattern
**LLM works entirely in tenant timezone (IST). Server auto-converts to UTC at edges. Zero timezone math for the LLM.**

## Helpers (server.py, above execute_tool)

```python
from datetime import timedelta
IST_OFFSET = timedelta(hours=5, minutes=30)

def _parse_ist_to_utc(dt_str):
    """Parse IST datetime string → UTC datetime for DB storage."""
    if not dt_str or not isinstance(dt_str, str):
        return None
    dt = datetime.fromisoformat(dt_str.replace(' ', 'T'))
    if len(dt_str) <= 10:  # date-only — caller applies default time
        return dt
    return dt - IST_OFFSET

def _format_utc_as_ist(dt_val):
    """Format UTC datetime → IST string for LLM display."""
    if dt_val is None:
        return "none"
    ist_dt = dt_val + IST_OFFSET
    return ist_dt.strftime('%b %d %I:%M %p IST')
```

## Tool Boundaries

| Tool | Input | Storage | Display |
|------|-------|---------|---------|
| `create_action` | IST (from LLM) | UTC (subtract IST_OFFSET) | — |
| `update_action` | IST (from LLM) | UTC (subtract IST_OFFSET) | — |
| `create_action_item` | IST (from LLM) | UTC (subtract IST_OFFSET) | — |
| `set_reminder` | delay_minutes (relative) | UTC (utcnow + delta) | — |
| `get_action_items` | — | — | IST (_format_utc_as_ist) |
| `query_actions` | — | — | IST |

Date-only input (no time component): default to 6 PM IST, THEN subtract IST_OFFSET to get UTC.
```python
if len(_due_raw) <= 10:  # date-only
    _due = datetime.fromisoformat(_due_raw).replace(hour=18, minute=0, second=0)
_due = _due - IST_OFFSET  # IST → UTC
```

## System Prompt

**Before** (9-line conversion table — removed):
```
IMPORTANT — All datetime values passed to tools MUST be in UTC. IST is UTC+5:30.
Examples: 9:00 AM IST = 03:30 UTC → pass "2026-06-17T03:30:00"
```

**After** (one line):
```
⏱ All times you see and pass to tools are in IST. The server handles UTC conversion automatically. You never need to convert timezones — just use IST everywhere.
```

## Verification
- "change check-in to 7 PM" → LLM passes `2026-06-16T19:00:00` (IST) → stored as `13:30:00 UTC` → displayed as "Jun 16 07:00 PM IST" ✅
- Date-only "Jun 17" → defaults to 6 PM IST → stored as `12:30 UTC June 17` ✅
