# Cron Validation & Scheduler Safety (June 2026)

This reference documents the validation and safety additions to the `set_cron` tool and the scheduler's reschedule loop, fixing infinite-loop and hallucinated-tool vulnerabilities discovered during the June 10, 2026 voice-pipeline debugging session.

## set_cron Tool Validation

**Location:** `server.py`, `execute_tool()`, ~line 4597

### Frequency Validation

Previously: any string was accepted as `frequency`. If the LLM passed `"monthly"`, the cron was created but the scheduler's reschedule loop would SPIN FOREVER (see Safety Limit below).

**Fix — validate frequency upfront:**
```python
if frequency not in ("daily", "weekdays", "weekly"):
    return "Error: 'frequency' must be one of: daily, weekdays (Mon-Fri), weekly"
```

### action_type Validation

Previously: any string was accepted as `action_type`. The LLM could pass `"morning_briefing"` or hallucinated types.

**Fix — validate action_type:**
```python
if action_type not in ("whatsapp_to_owner", "send_whatsap", "send_email", "internal_note", "morning_briefing"):
    return "Error: 'action_type' must be one of: whatsapp_to_owner, send_whatsap, send_email, internal_note, morning_briefing"
```

**The pattern:** every optional/string field that maps to a fixed set of enum values should be validated at the tool boundary. The LLM WILL pass invalid values — it's not a question of if, but when.

## Scheduler Safety Limit

**Location:** `server.py`, `_run_scheduler()`, ~line 8196

### The Bug

The reschedule loop:
```python
while _next <= utcnow():
    if _freq in ("daily", "weekdays"):
        _next += timedelta(days=1)
    elif _freq == "weekly":
        _next += timedelta(days=7)
```

If `_freq` was anything other than "daily", "weekdays", or "weekly" (e.g., "monthly" which wasn't caught because the set_cron validation was added LATER), the `while` loop advances `_next` by ZERO days → infinite loop at 100% CPU.

### The Fix

Two safety nets:

1. **Tool-level validation** (above) prevents bad frequencies from entering the DB
2. **Defensive fallback in the scheduler** in case a bad value slips through:
```python
_safety = 0
while _next <= utcnow():
    if _freq in ("daily", "weekdays"):
        _next += timedelta(days=1)
    elif _freq == "weekly":
        _next += timedelta(days=7)
    else:
        _next += timedelta(days=1)  # fallback for unknown frequency
    _safety += 1
    if _safety > 365:
        raise Exception(f"Cron reschedule exceeded safety limit (freq={_freq})")
```

The `else` clause handles unknown frequencies with a sensible default (daily). The `_safety` counter ensures the loop can never spin more than 365 iterations — even if ALL branches are missed, the exception fires.

**General principle:** Any `while` loop that depends on external input (user-provided config, LLM-generated args) must have a safety counter. A 3-line safety guard prevents a class of bug that would otherwise take down the server silently.
