# IST/UTC Clean Boundary — June 16, 2026

## Problem

The LLM worked in IST but had to manually convert to UTC for every tool call. A 9-line conversion table in the system prompt taught her to subtract 5:30. She forgot. Repeatedly.

**Failures traced to timezone confusion today:**
- "Push check-in to 5 PM" → action created at 10:30 PM IST (LLM passed `17:00:00` thinking 5 PM IST, server read as 5 PM UTC)
- "Change to 7 PM" → LLM dropped the time entirely, defaulted to 6 PM IST
- "Check-in for tomorrow 9 AM" → LLM passed date-only, defaulted to 6 PM IST

## Solution: Clean Boundary

```
User / LLM:  IST  ──→  Server converts to UTC  ──→  DB stores UTC
User / LLM:  IST  ←──  Server converts from UTC  ←──  DB stores UTC
```

### Helpers (server.py, before execute_tool)

```python
from datetime import timedelta as _IST_TD
IST_OFFSET = _IST_TD(hours=5, minutes=30)

def _parse_ist_to_utc(dt_str):
    """LLM passes IST → return UTC datetime for DB storage."""
    if not dt_str or len(dt_str) <= 10:  # date-only, caller applies default
        return datetime.fromisoformat(dt_str)
    return datetime.fromisoformat(dt_str.replace(' ', 'T')) - IST_OFFSET

def _format_utc_as_ist(dt_val):
    """DB UTC → return IST string for display to LLM."""
    if dt_val is None: return "none"
    return (dt_val + IST_OFFSET).strftime('%b %d %I:%M %p IST')
```

### Tool Handlers Updated

| Tool | Before | After |
|------|--------|-------|
| `create_action` | Stored LLM string as-is (UTC), date-only → 12:30 UTC | `_parse_ist_to_utc()`, date-only → 6 PM IST → 12:30 UTC |
| `update_action` | Stored LLM string as-is → SQLAlchemy TypeError | `_parse_ist_to_utc()` + `db.rollback()` recovery |
| `create_action_item` | Stored LLM string as-is | `_parse_ist_to_utc()` when time present |
| `get_action_items` | Showed `due: Jun 16 11:30 AM UTC` | Shows `due: Jun 16 07:00 PM IST` |

### Prompt Simplified

**Before (9 lines):**
```
All times MUST be in UTC. IST is UTC+5:30. SUBTRACT 5h30m.
Examples: 9 AM IST = 03:30 UTC, 5 PM IST = 11:30 UTC...
Before passing any time, verify: is this UTC or IST?
```

**After (1 line):**
```
⏱ All times you see and pass to tools are in IST. 
The server handles UTC conversion automatically. 
You never need to convert timezones — just use IST everywhere.
```

### Verification

```
"change check-in to 7 PM today"
  → get_action_items: "due: Jun 16 07:00 PM IST [id=0e494111]"
  → update_action: due_at=2026-06-16T19:00:00 (LLM passes 7 PM IST)
  → DB: 13:30:00 UTC (= 7 PM IST) ✅
  → Response: "already set for 7:00 PM IST" ✅
```

### Key Principle

Tool descriptions in AGENT_TOOL_SCHEMA are behavioral primer, not documentation. Any timezone math in the prompt WILL be applied incorrectly by the LLM at some point. Move conversion to code.
