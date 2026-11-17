# The `desc` Field Routing Gate — June 2026 Session (UPDATED: Post-Fix)

## Problem

Cold outbound cadence to Gregory Ipe (email-only lead) produced no email despite:
- Lead having valid email (gregipe@gmail.com)
- Cold template published with system prompt + email step
- All other steps appeared to function

## Root Cause (OLD behavior — now fixed)

Before the fix, `_schedule_cadence_for_lead()` used a `desc` field gate:

```python
if desc and not fields:   # ← desc="" → False for email step
    # LLM format — generates at send time
else:
    # Legacy format — pre-interpolates from fields
```

The email step had `desc=""` and `fields={}` → fell through to legacy format → created empty body → execution silently skipped.

## The Actual Fix (June 2026)

**Principle change, not a band-aid.** Greg's decision: **System prompt rules supreme.** WhatsApp & email always use LLM format. The `desc` gate is dead for these channels.

### Change 1: Scheduling Gate (`server.py` ~2495)

**Before:**
```python
if desc and not fields:
```
**After:**
```python
if channel in ("whatsapp", "email"):
```

WhatsApp & email steps ALWAYS enter LLM format. `fields` is ignored. Legacy format path only runs for `sms`, `call`, and other channels.

### Change 2: `_generate_step_message` (`server.py` ~2571)

**Before:**
```python
if not desc:
    return None  # No desc means legacy format
```
**After:**
```python
if not desc:
    desc = f"Step {step_index + 1} of {total_steps}: Send the {channel.upper()} message at this position in the sequence."
```

Auto-generates a step objective so the LLM knows which position in the sequence to write. The system prompt itself contains the full sequence text for each channel.

## What This Means

| Before | After |
|--------|-------|
| `desc` gated LLM vs legacy | Channel gates it: WhatsApp & email = LLM, others = legacy |
| Empty `desc` + empty `fields` = silent skip | Empty `desc` = auto-generates position-based objective |
| System prompt written but never consulted | System prompt is consulted for every WhatsApp & email message |
| Frontend step description was critical | Frontend fields are irrelevant for WhatsApp & email |

## Key Line Numbers (June 2026)

- Scheduling: `server.py` line 2495-2535
- Message generation: `server.py` line 2558-2664
- Execution LLM path: `server.py` line 6770-6911
- Execution legacy path: `server.py` line 6917-6961

## Verification

Trigger a cadence for a lead with only email:
```bash
curl -s -X POST "http://localhost:8766/api/cadence/trigger/lead/LEAD_ID" | python3 -m json.tool
```
Check that actions are created with `_format: "llm"` payload.
