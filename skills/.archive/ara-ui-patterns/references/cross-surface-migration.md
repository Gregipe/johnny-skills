# Cross-Surface Data Model Migration

Methodology for safely moving a concept from per-instance to global scope (or vice versa) across all UI/data surfaces.

## The Problem

A single concept (e.g., "Objective") touches multiple surfaces. Changing WHERE it lives (per-template → global, or vice versa) requires tracing every surface. Missing one means the old behavior leaks through — user sees stale data, broken switching, or contradictory labels.

## The Checklist — Map ALL Surfaces First

Before changing ANY code, enumerate every surface the concept touches:

### 1. Static HTML / Template Strings
- Search the template file for the concept name everywhere it appears
- Check: tab bars, section headers, chips, module lists, stat labels, overview pills, preview boxes
- **Don't just search visible text** — also search `id="..."`, `data-section="..."`, `data-tab="..."` attributes

### 2. Dynamic JS Rendering
- Functions that populate lists (`moduleDefs`, `checks[]`, chip arrays)
- Template rendering functions (`renderTemplates`, `renderCurrentTemplate`, `renderPromptOverview`)
- Event handlers that use the concept name

### 3. Data Model Definitions
- Default template definitions (template `promptParts`, template fields)
- Load/save functions (`loadPromptParts`, `collectPromptParts`, `saveCurrentState`)
- Migration / initialization logic (`migrateToGlobalPromptParts`)

### 4. Cached / Stale Data
- User's localStorage or saved template data may have old structure
- After refactoring the schema, old saved prompts (`t.systemPrompt`) may contain the concept in compiled text
- Solution: strip or migrate old data on load (regex in `loadPromptParts`)

### 5. Server Endpoints
- Validate/compile endpoints that receive prompt parts
- Preview generation endpoints
- Publish/save endpoints

### 6. Runtime Assembly
- The function that assembles the final output (`assembleSystemPrompt`)
- Any merge/split logic between global and per-template

## The Process

1. **MAP FIRST** — use grep to find every occurrence of the concept name across all surfaces listed above
2. **CATEGORIZE** — which occurrences should keep the concept (correct per-template usage) vs remove it (leaking into global)
3. **CHANGE ALL** — execute all removals in one batch
4. **VERIFY ON EVERY SURFACE** — reload the page, check tabs, aggregated views, diagnostics, live stats, every dialogue
5. **HANDLE STALE DATA** — old saved data will still have the old structure. Strip or migrate on load

## Session Example: Objective per-template → Global

The Objective was moved from per-template (stored in each template's promptParts) to per-template-but-global-outreach-template. The concept had to be removed from ALL these surfaces:

| Surface | What changed |
|---------|-------------|
| Main page overview chips | Removed "Objective" pill chip from Outreach Template |
| Prompt Builder tab bar | Removed 🎯 Objective tab |
| Architecture bar | Removed Objective step, renumbered (Brand=1, Sector=2, ... Final=F) |
| Module Breakdown diagnostics (static HTML) | Removed Objective `<li>` |
| Module Breakdown diagnostics (dynamic JS) | Removed `{key:'objective', name:'Objective'}` from `moduleDefs` |
| `loadPromptParts` | No longer loads `t.promptParts.objective` into builder |
| `collectPromptParts` | No longer includes `objective` in collected parts |
| `validateAndCompile` | No longer sends objective to server compilation |
| `saveCurrentState` | Removed `t.brandVoice` references (dead code from old model) |
| Cached system prompt | Regex strips `## Objective` section from old `t.systemPrompt` |
| Template switch handler | Uses `t.objective` for per-template tile, not global prompt |
| Outreach Template preview text | Shows `t.systemPrompt` (global) instead of `t.objective` |

## Key Lessons

- **Text search is not enough** — the concept may be in JS string literals, data arrays, and ID attributes
- **Static HTML and dynamic JS must both be updated** — the static HTML is the initial render; dynamic JS repopulates it
- **Cached data persists across page reloads** — old saved prompts need runtime stripping
- **Server endpoints receive different data** after the refactor — verify what gets sent
- **Template switching** can break if `saveCurrentState()` references removed DOM elements
- **User correction pattern**: if you change one surface and the user says "it's still there", check every other surface — you almost certainly only fixed one of N
