---
name: shared-ui-propagation
description: When modifying shared UI or doing text substitution across code paths, audit ALL occurrences (across files AND within files) to prevent orphaned stale values.
---

# Change Propagation & Substitution Verification

## 🚨 Cardinal Rule: "Do Work Deeply, Not Cosmetically"

This is the user's #1 operating principle — repeated verbatim from a correction. Violating it produces shallow fixes that leave old data rotting in other screens, which the user *will* catch and will *call you out* for. **Do not proceed past Phase 0 until you can list every surface the change touches.** When the user says "do work deeply," they mean trace every file, every code path, every data storage layer. If you catch yourself thinking "this is probably fine, I'll just fix the obvious file" — stop. You are about to make the same mistake.

## Trigger (grep before touch — always)
- Before modifying a shared UI component that appears on multiple pages
- Before doing any text/value substitution in a codebase (renaming labels, changing IDs, swapping names/companies)
- Any change that needs to hit multiple locations
- **Any term/ID/className/fieldName change at all** — even if it seems local. Always `grep -rn` the full project first. "It only appears once" is a living lie. The user expects you to THINK ACROSS SCREENS before touching anything — "do work deeply, not cosmetically." If you're not sure you found every surface, ASK. Do not assume. Do not fix one file and call it done.

**Cost of skipping Phase 0:** Multiple rounds of user frustration. The user will say "do work deeply," you'll go fix another file, they'll find another, you'll fix that, ad infinitum — each round eroding trust. The first fix should be the only fix. Phase 0 is how you achieve that.

### Cross-Layer API Format Drift (Backend → JS)

When a backend helper changes its output format, every JS consumer that post-processes that output can break silently. No error is thrown — the data just parses or renders incorrectly.

**Live example (June 2026):** `to_ist()` was upgraded from returning naive ISO strings (`2026-06-16T03:30:00`) to timezone-aware ISO strings (`2026-06-16T03:30:00+05:30`). The dashboard JS had `new Date(item.due_at + 'Z')` — appending `Z` to an already-timezoned string created `2026-06-16T03:30:00+05:30Z` which `new Date()` silently fails to parse (returns `Invalid Date`). All overdue items rendered as "pending" with wrong times — no console error, no stack trace.

**Audit step when changing any shared output helper:**
```bash
# After changing to_ist(), _format_utc_as_ist(), or any API response field:
# Find EVERY JS file that reads the changed field
grep -rn '\.due_at\|\.created_at\|\.scheduled_at\|to_ist\|_format_utc' static/*.js
# Verify no string concat like + 'Z' or + 'UTC' post-processes the new format
```

**Rule:** When a Python helper's output contract changes, audit every JS file that consumes it BEFORE declaring done. A silent `Invalid Date` in the browser is indistinguishable from correct rendering.

## The Two Kinds of Propagation Failure

| Type | Example Mistake | Fix |
|------|----------------|-----|
| **Across files** | Updating dashboard sidebar but missing the cadence page's copy. The ARA codebase has **mirrored template files** — `prompt_builder_template.py` and `prompt_editor_mod.py` are separate implementations imported by `cadence_template.py`. | Search every template file. Track the import chain: `grep -rn 'import\\|from.*import' *.py` to find all source files that could render the same component. If a page imports `from prompt_builder_template import PROMPT_BUILDER_HTML`, then that page renders that template too. |
| **Within a file** | Patching 1 of 6 JS code paths that all reference the same hardcoded string | Grep for the OLD string and verify ZERO remain |

## Steps

### Phase 0 — Map the surface area (DO THIS FIRST)
Before any grep, any patch, any code change:

1. **List every file that could be involved** — imported templates, duplicated implementations, JS callbacks, CSS classes, server routes
2. **For each file, note what layer it touches** — static HTML, dynamic JS, save/load, compile, cached data, preview
3. **If you can't list every file confidently** — ASK. The user would rather answer a question than discover you missed a file
4. **Check DATA LOADING as a separate surface** — Prefill/API data that fills form fields can OVERWRITE saved user data. The load function's merge strategy (replace vs deep-merge) is a distinct surface from the save function. Test: save → refresh → check fields still have saved values.
5. **Only then move to Phase 1**

This phase is THE lesson from Greg's "do work deeply, not cosmetically" correction. Skipping it produces surface-level fixes that leave old data rotting in other screens.

### Phase 1 — Discover all locations
```bash
# Find every file that references the thing you're changing
grep -rn 'old-value\|old-class\|old-label\|old-id' /Users/greg/ara/*.py | grep -v '.pyc' | grep -v '__pycache__'

# Count instances to know how many patches are needed
grep -c 'old-value' /Users/greg/ara/*.py
```

### Phase 2 — Apply changes
- For shared UI: update every template file that has a copy
- For string values: patch every instance — HTML templates, JS function call sites, fallback handlers, initial render state
- Use `replace_all=True` on patch ONLY when you've confirmed ALL instances are identical and should change

### Phase 3 — Verify zero old instances remain
```bash
# CRITICAL: confirm nothing was missed
grep -rn 'old-value' /Users/greg/ara/*.py
# Should return exit code 1 (no matches) and empty output

# Also check JS files if code was extracted
grep -rn 'old-value' /Users/greg/ara/static/*.js 2>/dev/null
```

## ⚠️ Cross-Page JS Environment Mismatch
A second class of propagation failure: **different pages load different JS bundles.**

| Page | Loads `dashboard.js`? | Has inline scripts? |
|------|----------------------|-------------------|
| Dashboard (`dashboard_template.py`) | ✅ Yes (`<script src="/static/dashboard.js?v=9">`) | Minimal |
| Cadence (`cadence_template.py`) | ❌ **No** | Extensive (inline `<script>` in `prompt_builder_template.py`) |
| Threads (`threads_template.py`) | ❌ **No** | Inline |

**Signal:** A shared UI component (modal, alert system, utility function) works on the dashboard but fails on the cadence page. The function simply doesn't exist because `dashboard.js` was never loaded.

**Required action:** When adding shared JS functionality that must work on ALL pages:
1. Identify every page that needs it
2. Check what JS each page loads
3. Either: (a) add the shared JS bundle to every page, or (b) inline the functionality in each page's inline script (with a guard to avoid duplicates)
4. Test on every page context, not just the one you're working on

**Example guard pattern** (from the B&W modal):
```javascript
(function() {
  if (document.getElementById('bwDialog')) return; // already created by dashboard.js
  // ... create dialog and attach to body ...
  if (!window.bwConfirm) {
    window.bwConfirm = function(msg) {
      // ... implementation ...
    };
  }
})();
```

## Context-Specific Checklist for ARA

### Shared UI (sidebar, nav, header, footer)
- `dashboard_template.py` — main dashboard (canonical source)
- `cadence_template.py` — outreach central / cadence builder
- `threads_template.py` — threads page
- Any other standalone page templates

### Template Variable Substitution (Python → HTML)
When a Python template file (e.g. `dashboard_template.py`) uses `{{VARIABLE}}` placeholders, the server endpoint that renders the template MUST perform the corresponding `.replace("{{VARIABLE}}", value)`. Missing substitutions produce broken frontends (literal `{{TENANT_TIMEZONE}}` passed to `new Date().toLocaleDateString()` → `RangeError: invalid time zone`).

**Pitfall:** Adding a new `{{VARIABLE}}` to a template but forgetting to add the `.replace()` in the endpoint. The template author and the endpoint author may be different people or different sessions.

**Fix pattern:** In `server.py`, the dashboard endpoint:
```python
# BEFORE (only replaces {{COMPANY}} — {{TENANT_TIMEZONE}} is literal):
return HTMLResponse(DASHBOARD_HTML.replace("{{COMPANY}}", "Hunar.ai"))

# AFTER:
return HTMLResponse(
    DASHBOARD_HTML
    .replace("{{COMPANY}}", "Hunar.ai")
    .replace("{{TENANT_TIMEZONE}}", "Asia/Kolkata")
)
```

**Audit step:** After adding `{{VARIABLE}}` to any template, grep the server endpoint to ensure every variable has a corresponding `.replace()`:
```bash
grep -o '{{[A-Z_]*}}' dashboard_template.py | sort -u  # all variables in template
grep '.replace(' server.py | grep -o '{{[A-Z_]*}}'  # all variables replaced
```

### ⚠️ Three Prompt Builder Template Files
The ARA codebase has **three** separate prompt builder implementations. When refactoring any prompt-builder feature, search ALL three:

1. `cadence_template.py` — inline overlay (opens from Outreach Central)
2. `prompt_builder_template.py` — full-screen slide-over (imported by cadence_template.py)
3. `prompt_editor_mod.py` — alternative inline variant

Changes to one do NOT propagate. Always grep across all three:
```bash
grep -rn 'fieldName|className|sectionName' /Users/greg/ara/*.py | grep -v '.pyc'
```

### Blank Section Debugging
See `references/blank-sector-tab-debugging.md` for the five failure modes when a Prompt Builder section appears blank despite prefill data: (1) object-to-string serialization producing `[object Object]`, (2) collapsed cards with no textarea elements, (3) missing load/collect function entries, (4) prefill guard checking the wrong field, and (5) duplicate element IDs where `document.getElementById` hits the hidden builder instead of the visible one.

For chip button interactivity issues (tone/language chips not clicking, wrong visual selection), see `references/chip-interactivity-debugging.md`.

### Hardcoded preview/display values
- Initial HTML render (template literal in Python string)
- JS `generatePreview()` function (shows loading state)
- JS `selectStep()` function (shows selected step lead)
- JS template switch handler (resets on template change)
- JS `staticFallback()` function (fallback defaults)
- JS step picker handler
- JS drag-drop reorder handler

### State/Stage transitions
- Inbound handler (`_handle_inbound_whatsapp`)
- Outbound handler (`_handle_outbound_whatsapp`)
- Scheduler (`_execute_action`)
- Manual API endpoints (`update_lead`)

## Antipatterns

- ❌ Assuming only one page has the component
- ❌ Patching the first match and stopping
- ❌ Only checking the page/code path you're currently testing
- ❌ Using `replace_all=true` without first counting occurrences
- ❌ Not restarting the server to pick up template changes
- ❌ Not hard-refreshing the browser (Cmd+Shift+R)

## Reference

See `references/rajesh-gregory-ipe-case.md` for a concrete failure example — 1 of 6 text instances patched, leaving 5 stale copies in the same file.

See `references/js-onclick-escaping.md` for the JavaScript onclick escaping pitfall — `\\'` sequences in Python-generated JS strings that generate HTML with inline event handlers. This is the most common cause of "page goes blank / nothing is clickable." Fix: use `data-` attributes instead of embedding values via string concatenation.

See `references/innerhtml-script-pitfall.md` for the innerHTML script execution pitfall — browsers silently ignore `<script>` tags injected via innerHTML. Fix: call the function directly after the innerHTML assignment, never embed a script tag.

See `references/sql-null-comparison-pitfall.md` for the SQL NULL comparison pitfall — another propagation failure class where fixing a NULL-safe query in one code path leaves identical bugs in others.

## Verification

```bash
# Final sanity check — zero old values anywhere
grep -rn 'old-value' /Users/greg/ara/
echo "Exit code 1 = CLEAN | Exit code 0 = LEFTOVERS"
```
