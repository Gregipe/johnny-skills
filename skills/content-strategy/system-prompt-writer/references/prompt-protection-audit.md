# System Prompt Protection Audit (June 2026)

## Background

The system prompt in ARA's cadence system was being silently overwritten by the `publish-global` endpoint. This endpoint broadcasts the cold template's `systemPrompt` and `promptParts` to ALL THREE templates (cold, inbound, nurture). The main page's `publishCadence()` was calling `publish-global` on every step publish, meaning every time a user changed step counts/timing, the system prompt got overwritten across all templates.

## Root Cause Chain

1. `publishCadence()` in cadence_template.py called `POST /api/cadence/publish` (saves steps) followed by `POST /api/cadence/publish-global` (overwrites all prompts)
2. The publish endpoint originally did `existing.config = template` — replacing the entire config with only the data from the frontend. This dropped `promptParts`, `steps`, `conditions`, etc.
3. My intermediate fix only saved 3 fields (`promptParts`, `systemPrompt`, `title`), dropping `steps` — which made the "Publish Cadence" button silently lose step configurations
4. The final fix merges ALL template fields: `for k, v in template.items(): merged[k] = v`

## Fix Applied

### server.py — publish endpoint
- Changed from `existing.config = template` to merging: `merged = dict(existing.config or {}); for k, v in template.items(): merged[k] = v`
- This preserves all template fields (steps, conditions, promptParts, systemPrompt, etc.)

### cadence_template.py — publishCadence()
- Removed the `publish-global` fetch call inside `publishCadence().then()`
- The main page publish now only calls `/api/cadence/publish` — it does NOT overwrite other templates' prompts

### cadence_template.py — savePromptAndClose()
- Removed the `publish-global` fetch call from the legacy prompt editor
- This function is dead code (no UI opens `openPromptEditor()` anymore), but removed for safety

### prompt_builder_template.py — compilePbPrompt()
- Added fallback to read sections from `t.systemPrompt` when DOM textareas are empty
- Sections like Objective, Lead Context, Industry, FOMO, Message Structure, Sequence, and Communication Rules don't have dedicated tab textareas — these now fall back to the system prompt content
- Added "Objective" to the missing-sections list

## Remaining Risk

The `POST /api/cadence/publish-global` endpoint still exists in server.py as an API endpoint. No UI code calls it anymore:
- `publishCadence()` — removed ✅
- `savePromptAndClose()` — removed ✅
- `publishPromptBuilder()` — still calls it, but saves `previous_systemPrompt` first ✅

If a future feature adds a new caller, it must be reviewed for protection.

## Verification

All three templates now have independent system prompts and promptParts. Publishing step changes from the main page no longer cross-contaminates prompts.
