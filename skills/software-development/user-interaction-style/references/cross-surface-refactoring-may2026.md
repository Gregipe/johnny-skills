# Cross-Surface Data-Model Refactoring — May 2026 Case Study

## The Task

Split the Outreach Template's data model: Objective becomes per-template (each of Outbound/Inbound/Nurture has its own objective), while Brand/Sector/Security/Channels become global (shared across all templates).

## What Went Wrong

Surface-level fixes — removed the Objective tab from the Prompt Builder and the chip from the overview row — but missed Objective persisting in **3 other layers**:

### Layer 1: Static HTML (Module Breakdown diagnostics panel)

File: `cadence_template.py`
Line: `849` (removed) — `<li><span class="module-name"><span class="prompt-status-dot ok"></span>Objective</span><span class="module-tokens">—</span></li>`

This was in the aggregated tab's right sidebar, showing a module breakdown. Never checked because "the chips are gone."

### Layer 2: Dynamic JS (moduleDefs array)

File: `cadence_template.py`
Line: `1882` (removed) — `{key:'objective', name:'Objective', color:'#34c759'},`

This array populates the Module Breakdown when `validateAndCompile()` runs. Even after removing the static HTML, the dynamic JS would re-inject Objective on validation.

### Layer 3: Cached data (old t.systemPrompt)

File: `cadence_template.py`
Line: `1783-1784` — Old saved system prompts contained `## Objective\n...` section. The `loadPromptParts()` function displayed `t.systemPrompt` verbatim in the Aggregated tab. Fix: strip `## Objective` on display.

### Bonus: Dead DOM references in saveCurrentState()

File: `cadence_template.py`
Line: `1316-1324` — `saveCurrentState()` tried to read from `#toneChips`, `#nonosContainer`, `#formalitySlider` which no longer existed (removed when Brand Voice was globalized). Crashed on template switch, making Inbound/Nurture cards unclickable.

### Bonus: Preview text showing objective

File: `cadence_template.py`
Line: `2063` — `doLoadTemplate` showed `t.objective` in the Outreach Template's preview box. Should have shown `t.systemPrompt` (global prompt without objective).

## Discovery Sequence

| Step | What I checked | Result |
|------|---------------|--------|
| 1 | Prompt Builder tabs | Clean — removed earlier |
| 2 | Architecture bar | Clean — removed earlier |
| 3 | Overview chips | Clean — removed earlier |
| 4 | Module Breakdown (vision) | Not visible in screenshot |
| 5 | Module Breakdown (DOM text) | ❌ FOUND — static HTML + dynamic JS |
| 6 | Aggregated prompt text | Clean — no Objective in rendered prompt |
| 7 | Full builder text content sweep | ❌ FOUND — stale `t.systemPrompt` data |
| 8 | saveCurrentState error on template switch | ❌ FOUND — dead brandVoice refs |

## Verification Pattern

After ALL fixes applied:

```javascript
// Text content sweep catches everything
document.getElementById('promptEditorOverlay').textContent.indexOf('Objective')
// → -1 (CLEAN)

// Module list DOM check
Array.from(document.querySelectorAll('#diagModuleList li'))
  .map(l => l.textContent.trim())
// → ['Brand & Personality—', 'Sector Intelligence—', 'Security & Guardrails—', 'Channel Logic—']
```

## Fixes Applied (in order)

1. `saveCurrentState()` — removed `t.brandVoice` and `systemPromptInput` references
2. Static HTML — removed Objective `<li>` from `diagModuleList`
3. Dynamic JS — removed `{key:'objective', ...}` from `moduleDefs`
4. Cached data — added regex to strip `## Objective` section from old `t.systemPrompt` in `loadPromptParts()`
5. Preview text — changed `doLoadTemplate` to show `t.systemPrompt` instead of `t.objective`

---

## Part 2: The Triple-File Discovery (May 29, 2026)

The first pass of fixes only touched `cadence_template.py` — the file where the "/cadence" page's inline Prompt Builder lives. But Greg **still saw Objective** after a hard refresh.

### The Root Cause

The `/cadence` page's `CADENCE_HTML` template (from `cadence_template.py`) imports `PROMPT_BUILDER_HTML` from `prompt_builder_template.py` at line 3. Additionally, a third file `prompt_editor_mod.py` also contains a Prompt Builder variant. Each file had its OWN copy of the Objective tab, architecture bar, diagnostics panel, and module definitions.

### File Inventory of Prompt Builder Implementations

| File | Prompt Builder type | Line count | Had Objective? |
|------|-------------------|------------|----------------|
| `cadence_template.py` | Inline modal (on /cadence page) | ~2500 | ✅ Fixed in Part 1 |
| `prompt_builder_template.py` | Slide-over modal (sidebar + workspace layout) | ~1050 | ❌ Still had Objective — sidebar nav item, arch bar step 1, tab body, section chip, live stats module, JS defs, load/save functions |
| `prompt_editor_mod.py` | Inline modal (separate variant) | ~500 | ❌ Still had Objective — tab bar item, section chip, tab body, load/save functions, prefill guard, preview text |

### What Each File Had (that I missed on first pass)

**prompt_builder_template.py:**
- `data-pb-tab="objective"` — sidebar navigation item with active state
- `data-tab="objective"` — architecture bar step 1 (numbered, with checkmark)
- `id="pbTab-objective"` — full tab body with North Star Objective textarea, Success Metrics chips, and 4 behavior sliders (Aggressiveness, Persistence, Formality, Speed vs Precision)
- `data-section="objective"` — section chip in final prompt toolbar
- `<li>Objective <span class="pb-live-tokens">—</span>` — live stats module breakdown
- `{key:'objective', name:'Objective'}` — dynamic module defs array
- `setVal('pe_objective', ...)` — JS load function
- `objective: gv('pe_objective')` — JS collect/save function
- `if (!pp.objective && !cache.objective)` — prefill guard

**prompt_editor_mod.py:**
- `data-tab="objective"` — tab bar entry
- `data-section="objective"` — section chip in aggregated view
- `id="tab-objective"` — full tab body with Cadence Objective textarea
- `setVal('pe_objective', ...)` — JS load function
- `objective: gv('pe_objective')` — JS collect/save function
- `parts.objective.substring(...)` — preview text fallback
- `t.promptParts.objective` — prefill guard check

### Why I Missed Them

1. **Assume-one-file fallacy** — when we discussed "the Prompt Builder," I mentally mapped it to `cadence_template.py` because that's where the "Open Builder" button is. Didn't check which other files the page imports.
2. **curl | grep blind spot** — the initial `grep -rn 'Objective' cadence_template.py` showed it was clean, so I declared victory. But the rendered page was importing from TWO other files.
3. **Imports chain not traced** — `cadence_template.py` line 3: `from prompt_builder_template import PROMPT_BUILDER_HTML`. Never checked what that import brought in.

### Fix Applied

All three files patched in a single commit. Verification:

```bash
curl -s http://localhost:8766/cadence | grep -c 'data-tab.*objective'
# → 0 (CLEAN)
```

### Lesson: The Import Chain Check

When doing cross-surface refactoring in **any** project, before touching code:

```bash
# Step 1: Find every reference to the term across ALL files
grep -rn 'oldFieldName\|oldSectionName' /project/*.py | grep -v '.pyc\|__pycache__'

# Step 2: Trace imports — which files include which?
grep -rn 'import.*template\|from.*import.*HTML\|include\|extend' /project/*.py | head -30

# Step 3: Check the rendered output, not just the source files
curl -s http://localhost:8766/page | grep -c 'oldTerm'

# Step 4: If multiple files match, edit ALL of them, not just the main one
```

**The GREP should cover the entire project directory, not just the file you think is relevant.**
