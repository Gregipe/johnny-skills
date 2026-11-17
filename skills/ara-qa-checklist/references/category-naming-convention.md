# Category Naming Convention — Cross-Layer Consistency

## The Bug

The LLM saved skills with `"category": "gtm_learnings"` (plural with 's') but the backend state checker looked for `"gtm_learning"` (singular). Result: **19 valid skills were invisible** — the state showed 0 skills for the module despite 19 being saved.

## Affected Layers

| Layer | File | Location |
|-------|------|----------|
| **LLM System Prompt** | `induction_engine.py` | `===SAVE_SKILL===` example JSON uses whatever category the prompt defines |
| **Backend State Checker** | `induction_engine.py` → `get_induction_state()` | `categories` dict keys |
| **Backend Dashboard** | `server.py` | `categories` dict in dashboard template |
| **Frontend Tabs** | `induction_template.py` | `data-tab="..."`, `MODULES` array, `MODULE_NAMES` keys, `switchTab()` calls |
| **Frontend Module Bars** | `induction_template.py` | `id="moduleBar-{category}"`, `id="modulePct-{category}"` |
| **Frontend Sidebar** | `induction_template.py` | `id="count-{category}"`, `id="icon-{category}"` |

## Fix Pattern

1. Choose ONE canonical category name per module (e.g., `gtm_learnings` not `gtm_learning`)
2. Update ALL layers to use exactly that name
3. The LLM prompt's `===SAVE_SKILL===` example must use the canonical name
4. The state checker's `categories` dict must use the canonical name
5. All frontend HTML IDs, data attributes, and JS objects must use the canonical name

## Search Command

```bash
grep -rn "gtm_learning\|gtm_learnings" /Users/greg/ara/ --include="*.py"
```

This will find all occurrences and reveal mismatches.
