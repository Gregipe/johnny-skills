
### Bug 7: migrateToGlobalPromptParts() wipes t.promptParts on every page load
**File:** `cadence_template.py` line ~1694
**Sign:** Data saved correctly (API + DB + localStorage confirmed), but on refresh, `localStorage['ara_cadence_data']['cold'].promptParts` is `{}`. User's data is completely gone.
**Root:** `renderCurrentTemplate()` → `migrateToGlobalPromptParts()` runs on every page load. It copies data to `globalPromptParts`, then wipes `tmpl.promptParts = {}` for ALL templates, then calls `saveData()` to persist the empty state. The full-screen Prompt Builder reads from `t.promptParts`, not `globalPromptParts`, so the builder only ever sees empty data after refresh.
**Detection:** Check `migrateToGlobalPromptParts.toString().includes('tmpl.promptParts = {}')` in browser console — `true` = bug is active.
**Fix:** Remove the clearing loop entirely. The data belongs in `t.promptParts` — the migration to `globalPromptParts` was for the old editor, the new builder reads from promptParts.

### Bug 8: prefillFromInduction() overwrites saved data
**File:** `cadence_template.py` line ~2054
**Sign:** After refresh, prefill values appear instead of user's saved values. User saves → sees "✓ Saved" → refreshes → prefill data is back.
**Root:** Called by `renderCurrentTemplate()` on every page load. Fetches prefill API → sets `globalPromptParts = prefill_data` → calls `loadPromptParts(t)` which reads from `globalPromptParts` → calls `saveData()`.
**Fix:** Add early-return guard — if `t.promptParts` already has brand data (saved by user), skip the prefill fetch entirely. The check: `if (t.promptParts && Object.keys(t.promptParts).length > 0 && t.promptParts.brandPersonality && Object.keys(t.promptParts.brandPersonality).length > 2) return;`
