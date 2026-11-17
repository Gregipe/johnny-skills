# Playbook Custom Actions & @-Mention Integration

## Session: May 30, 2026

## What Was Built

### 1. Double-Quote HTML Attribute Fix
**File:** `cadence_template.py`
**Line:** ~2298

The "then" text input in follow-up rules rendered `value="' + (r.then || '') + '"` — double-quotes in user text broke the HTML attribute, truncating all content after the first `"`. No console error — just silently truncated values that looked like "save didn't stick."

**Fix:** `.replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;')` on the value interpolation.

**Detection recipe:** Type `test "quoted" text` in the input, save, close, reopen. If it shows `test ` (truncated at quote), this is the bug.

### 2. Custom Actions (addAction/editAction/removeAction)
**File:** `cadence_template.py`

- `addAction()` — prompt for name, create action with empty desc, render + preview
- `editAction(idx)` — prompt for updated name only (desc is inline editable)
- `removeAction(idx)` — confirm, splice from array, re-render
- `updateActionDesc(el)` — auto-save textarea oninput to data model

**Line numbers (approximate):** 2595-2620 (addAction), 2622-2635 (editAction), 2637-2648 (updateActionDesc), 2650-2660 (removeAction)

### 3. Inline Textarea for Action Descriptions
**File:** `cadence_template.py`

Changed from `<span class="pb-action-sub">desc</span>` to:
```html
<textarea class="pb-action-desc" data-idx="0" placeholder="Describe..." 
  oninput="updateActionDesc(this)">escaped description text</textarea>
```

**CSS:**
```css
.pb-action-info { flex:1;display:flex;flex-direction:column;gap:2px;min-width:0; }
.pb-action-desc { width:100%;border:none;background:transparent;font-size:11px;
  color:#6E6E73;resize:vertical;min-height:20px;padding:2px 0;font-family:inherit;
  line-height:1.4;outline:none; }
.pb-action-desc:focus { color:#111; }
```

### 4. @-Mention Integration in Playbook
**File:** `cadence_template.py` (listener), `prompt_builder_template.py` (functions)

The existing @-mention functions (`createMentionDropdown`, `showMentionDropdown`, `insertMention`, `closeMentionDropdown`) are global — declared at top level in `prompt_builder_template.py`. Added a parallel `input` listener scoped to `#playbookWorkspace .pb-action-desc` textareas.

**Key detail:** The click handler for `.mention-item` is document-wide (also in `prompt_builder_template.py`) so mention selections from the playbook dropdown work automatically.

**No separate asset picker needed** — user types `@` in the description textarea, sees the mention dropdown, picks a document/contact. Results in `@AssetName` embedded in the description text. The description is a textarea so @-mentions render as text with the dropdown support.

### 5. Main Page Stage Summary
**File:** `cadence_template.py`

Added `renderMainPagePlaybook()` that queries playbook data per stage and renders action/rule/escalation counts below the stage pills on the main Outreach Central page. Called from `closePlaybook()` and page init.

**Container:** `<div class="playbook-summary" id="playbookSummary">` in the HTML template (~line 770).

### 6. "+ Add Action" Button Wiring
Previously `showToast('Add action — coming soon')`. Changed to `addAction()`.

## Hard-Refresh Pitfall

Every time `cadence_template.py` is modified (HTML/CSS/JS changes), the **server restart alone does NOT update the browser** — the page was cached. The user must **Cmd+Shift+R** (hard refresh) to get the latest HTML/JS. This cost ~1 hour of debugging in this session because stale JS appeared to not have the fix.

**Rule:** After ANY HTML/JS template change in `cadence_template.py` or `prompt_builder_template.py`, explicitly tell the user to hard refresh before testing. Do not debug without confirming fresh code.
