# Cadence Scheduling: Desc Gate → Channel Gate (June 2026)

## The Problem

The `desc` field was the gate between LLM-format and legacy-format scheduling:

```python
# OLD — line 2495
if desc and not fields:
    # LLM format
else:
    # Legacy format — empty body, silent skip
```

Greg removed the step description textarea from the frontend UI. When published, `desc=""` caused ALL steps to hit the legacy path. For email (no fields), this produced `payload = {"subject": "Follow-up", "body": ""}`. At execution:

```python
# OLD — line 6930
if lead and lead.email and body:  # body="" → False → silent skip
```

The action was logged as `status: "completed"` with no error. No email sent, no error shown.

## The Fix: Two Changes in server.py

### Change 1: Scheduling Gate (line 2496)

```python
# NEW — WhatsApp & email always use LLM format
if channel in ("whatsapp", "email"):
    payload = {
        "_format": "llm",
        "_step_desc": desc,
        "_step_index": i,
        "_total_steps": len(steps),
        "_repeat_idx": r,
        "_total_repeats": repeat_count,
    }
else:
    # Legacy format for call/sms/other
```

**Rationale:** The system prompt contains the full sequencing for each channel (WhatsApp Message 1-5, Email 1-4+). No frontend fields override message content. The LLM reads the sequence from the system prompt at send time.

### Change 2: Message Generation (line 2572)

```python
# OLD
if not desc:
    return None  # Crashed LLM path → error "LLM generation returned None"

# NEW
if not desc:
    desc = f"Step {step_index + 1} of {total_steps}: Send the {channel.upper()} message at this position in the sequence."
```

This gives the LLM positional context to read the correct message from the system prompt's channel sequencing.

## Missing Steps Array

The scheduler does `steps = template.get("steps", [])` then `if not steps: return`. A published config with only `promptParts` + `systemPrompt` (no `steps` array) silently skips all scheduling.

**Root cause:** The `publish-global` endpoint overwrites `promptParts` and `systemPrompt` but preserves existing `steps`. A fresh publish from the new UI (which removed the step builder entirely) never included steps. The config ended up with no steps.

**Fix:** Generate default steps from the sequencing metadata in `promptParts.channelSpecific` when steps are missing from the config.

## Publish Flow (Frontend → Backend)

1. `publishCadence()` calls `fetch('/api/cadence/publish', {template_id, template})` — saves full template including steps
2. On success, calls `fetch('/api/cadence/publish-global', {promptParts, compiled_prompt})` — overwrites promptParts + systemPrompt on ALL templates, preserves existing steps/conditions/title
3. `publish_global` does `existing.config["promptParts"] = prompt_parts; existing.config["systemPrompt"] = compiled_prompt` — does NOT touch other keys

## What the Frontend Publishes

`getTemplate()` returns the full template object from localStorage (merged from DEFAULT_TEMPLATES):

```javascript
// DEFAULT_TEMPLATES.cold has 3 default steps
cold: {
  steps: [
    {channel:'whatsapp', delay_hours:0, repeat_count:1, interval_hours:0, desc:'...'},
    {channel:'email', delay_hours:4, repeat_count:1, interval_hours:0, desc:'...'},
    {channel:'call', delay_hours:48, repeat_count:1, interval_hours:0, desc:'...'}
  ],
  promptParts: {...},
  systemPrompt: '...',
  brandVoice: {...},
  conditions: {...}
}
```

If localStorage is stale or missing, `fetchFromServer()` loads `promptParts` and `systemPrompt` from the published config but does NOT touch `steps`. Steps always come from DEFAULT_TEMPLATES or localStorage.

## Key Debugging Points

| Symptom | Check |
|---------|-------|
| No actions created for lead | DB: cold template config has `steps`? |
| Action created with empty body | Scheduling path: LLM format vs legacy? |
| Action completed but nothing sent | Execution path: `body=""` skips at line 6930 |
| Greg says "I published, it didn't work" | Check if steps array is present in published config |
| Ava says "no steps configured" | That's the exact symptom of missing steps array |
