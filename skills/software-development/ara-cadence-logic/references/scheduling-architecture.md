# ARA Scheduling Architecture

## Three-Layer Architecture

1. **Frontend** (`cadence_template.py`) — Step cards with timing inputs. `fetchFromServer()` loads published config.
2. **Publish API** (`server.py:1967`) — `/api/cadence/publish` saves template to `CadenceConfig`. Then `/api/cadence/publish-global` overlays `promptParts` + `systemPrompt` on all templates (preserving each template's steps, conditions, brandVoice, etc.).
3. **Scheduler** (`_schedule_cadence_for_lead`, `_execute_action`, `_generate_step_message`) — Reads steps, creates `ScheduledAction` per repeat, executes at fire time with LLM-generated content.

## Step Data Model (Post-Desc-Removal, June 2026)

Steps contain ONLY timing and channel — no content fields:

```python
{
    "channel": "whatsapp",       # or "email"
    "delay_hours": 0,            # hours before first fire
    "repeat_count": 8,           # number of repeats
    "interval_hours": 1,         # hours between repeats
}
```

No `desc`, no `fields`. The system prompt's `channelSpecific.<channel>.sequencing` field tells the LLM what to write at each position.

## LLM Format Gate (server.py:2496)

```python
if channel in ("whatsapp", "email"):  # ALWAYS LLM format
    payload = {
        "_format": "llm",
        "_step_desc": desc or "",
        "_step_index": i,
        "_total_steps": len(steps),
        "_repeat_idx": r,
        "_total_repeats": repeat_count,
    }
```

All other channels → legacy format (pre-interpolated fields). Call is deferred.

## `_generate_step_message` (server.py:2558)

Generates message at send time using system prompt + lead context. When `desc` is empty:
```python
if not desc:
    desc = f"Step {step_index + 1} of {total_steps}: Send the {channel.upper()} message at this position in the sequence."
```

The system prompt's sequencing field contains Message 1, 2, 3... objectives that the LLM reads.

## Channel Requirements (server.py:2470-2485)

- **WhatsApp/sms**: requires `lead.phone` (non-empty, non-whitespace). Skipped silently.
- **Email**: requires `lead.email` (non-empty, non-whitespace). Skipped silently.

## `_next_working_time` Clumping Bug (server.py:2316)

When working hours enabled (9AM-6PM IST), all repeats outside working hours clamp to 9AM next day. Cause: `dt.replace(hour=9) + timedelta(days=1)` loses time offset. Fix: preserve offset from 18:00.

## `fetchFromServer()` Fix (cadence_template.py:1168, June 1 2026)

The cadence page now ALWAYS merges from published config:

```javascript
tmpl.promptParts = JSON.parse(JSON.stringify(sv.promptParts));
tmpl.systemPrompt = sv.systemPrompt || tmpl.systemPrompt;
if (sv.steps && sv.steps.length > 0) {
    tmpl.steps = JSON.parse(JSON.stringify(sv.steps));
}
['brandVoice', 'conditions', 'stopConditions', 'objective'].forEach(k => {
    if (sv[k] !== undefined) tmpl[k] = JSON.parse(JSON.stringify(sv[k]));
});
```

**Previous bug:** `fetchFromServer` only merged if `tmpl.promptParts` was empty — steps ALWAYS came from `DEFAULT_TEMPLATES`. So Greg would set timing, publish (saved correctly), but next page load showed defaults.

## Triggering Cadence (server.py:2667)

`POST /api/cadence/trigger/lead/{lead_id}` calls `_schedule_cadence_for_lead`:
1. Loads lead + `cadence_type`
2. Loads published config for that cadence type
3. Checks stage — skips if engaged/qualified/meeting_booked/dormant/lost
4. Checks existing pending actions — skips if any exist
5. Iterates steps, checks channel requirements, creates `ScheduledAction` per repeat
6. Sets lead stage to `reached_out`

## Default Step Sequencing Counts (June 2026)

From the published promptParts for the Cold Outbound template:
- **WhatsApp**: 5 sequence descriptors (Message 1-5)
- **Email**: 6 sequence descriptors (Email 1-6)
- Users can set any repeat_count in the frontend; the system prompt describes what should happen at each position.

## Related

Part of `ara-cadence-logic` umbrella.
