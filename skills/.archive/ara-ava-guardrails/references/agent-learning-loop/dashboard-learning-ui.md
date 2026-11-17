# Dashboard UI — Skills Dashboard (May 30, 2026 — v2 Upgrade)

The Skills Dashboard (Learnings nav item → Skills tab) was upgraded on May 30 to include source tracking, search, source filter tabs, and a detail slide-out panel.

## API Endpoints Used (v2)

| Endpoint | Purpose | Called By |
|----------|---------|-----------|
| `GET /api/learning/stats` | Experience card stats (total_skills, total_insights, pending_review, avg_confidence) | `renderLearnings()` |
| `GET /api/skills?limit=150` | All skills with source, category, key, value, created_at | `renderLearnings()` — cached in `cp._skillsCache` |
| `GET /api/learning/notifications?acknowledged=false` | Activity feed entries | `renderLearnings()` — for the Activity tab |

**Note:** The v1 implementation used `/api/insights/stats` and `/api/insights/learnings` from the `ava_insights` table. v2 uses `/api/skills` and `/api/learning/stats` from the `skills` table directly. The `skills` table now has a `source` column (`induction | document | conversation`) set at creation time and returned in the API response.

## Source Field in API Response

```json
{
  "id": "abc12345",
  "category": "proposition",
  "key": "logistics_segment",
  "value": "For logistics companies like Blue Dart, we reduce hiring TAT...",
  "confidence": 0.85,
  "source": "document",    // ← NEW: induction | document | conversation
  "created_at": "2026-05-30T20:45:00",
  "updated_at": "2026-05-30T20:45:00"
}
```

Added via the model `source = Column(String, default="induction")` in `database.py` and returned in the list endpoint with `"source": s.source or "induction"`.

## DB Migration

```sql
ALTER TABLE skills ADD COLUMN source VARCHAR DEFAULT 'induction';
```

Backfill for existing skills (no migration framework — raw SQLite):
```sql
UPDATE skills SET source = 'induction' WHERE category IN ('proposition', 'gtm_learnings', 'inbound', 'guardrail', 'coaching_objection');
UPDATE skills SET source = 'conversation' WHERE category IN ('objection_pattern', 'messaging_win', 'segment_signal', 'timing_pattern', 'learning_summary');
```

All creation paths updated to set source: `induction_engine.py` sets `source="induction"`, `document_skills.py` sets `source="document"`, `extract_conversation_learnings.py` sets `source="conversation"`.

## renderLearnings() — v2 Implementation

The function lives in `static/dashboard.js` (cache-busted with `?v=10`). It:

1. Fetches all 3 endpoints in parallel via `Promise.all()`
2. Counts skills by source and new-today by comparing `created_at` to `new Date().toDateString()`
3. Builds the page with experience card, 3 tabs (Insights, Skills, Activity)

**Skills tab content is built by `buildSkillsHtml(skills, sourceFilter, searchTerm)`:**
- Filters skills by source and search term
- Groups by category (priority order: proposition, gtm_learnings, inbound, guardrail, objection_pattern, messaging_win, segment_signal, timing_pattern, ...)
- Each category rendered as a `.sk-group` with `.sk-group-title` (icon + name + count)
- Each skill as `.sk-card` with: key (underscores → spaces), value, source badge, timestamp, NEW indicator (blue left border if created today)
- Click on a card → `openSkillDetail(id)` opens the detail overlay

**Source filter tabs** (`.skills-source-tab`):
- All, 💬 Induction (`, document`, 📄 Document, 🔄 Conversation
- Each shows count. Clicking calls `filterSkills(source, el)` which re-caches + rerenders via `buildSkillsHtml()`
- Active tab gets `.active` class (dark background)
- State variables `_skSource` and `_skSearch` persist filter across rerenders

**Search bar** (`.skills-search`):
- Input with `oninput="filterSkillsSearch()"` — filters by key + value lowercase match
- Calls `buildSkillsHtml(skills, _skSource, _skSearch)` on every keystroke

**Detail overlay** (`.sk-detail-overlay` + `.sk-detail-backdrop`):
- Rendered as static HTML in `dashboard_template.py` (hidden by default)
- `openSkillDetail(id)` populates: category, key (underscores → spaces), full value, source label, timestamp
- Related skills section shows up to 5 skills from the same category (excluding current)
- Clicking a related skill navigates the overlay to that skill
- `closeSkillDetail()` hides both overlay and backdrop
- Close via ✕ button or backdrop click

## CSS Classes (v2 additions)

Added to `dashboard_template.py` `<style>` block:

```css
.skills-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:20px; }
.skills-stats { display:flex; gap:20px; }
.skills-stat, .skills-stat-num, .skills-stat-label { ... }
.skills-search { display:flex; align-items:center; background:#fff; border:1px solid #E5E5E7; border-radius:10px; padding:8px 14px; margin-bottom:16px; gap:8px; }
.skills-source-tabs { display:flex; gap:8px; margin-bottom:18px; flex-wrap:wrap; }
.skills-source-tab { padding:5px 12px; border-radius:16px; font-size:11px; font-weight:500; border:1px solid #E5E5E7; background:#fff; color:#6E6E73; cursor:pointer; }
.skills-source-tab.active { background:#111; color:#fff; border-color:#111; }
.sb-badge { font-size:9px; font-weight:600; padding:2px 7px; border-radius:8px; text-transform:uppercase; }
.sb-document { background:#E8F4FD; color:#1A73E8; }     /* Blue */
.sb-induction { background:#F0FDF4; color:#16A34A; }    /* Green */
.sb-conversation { background:#FEF3C7; color:#D97706; }  /* Yellow */
.sk-new { border-left:3px solid #2563eb; }
.sk-group { margin-bottom:24px; }
.sk-group-title { font-size:13px; font-weight:600; border-bottom:1px solid #E5E5E7; display:flex; align-items:center; gap:6px; }
.sk-card { background:#fff; border:1px solid #E5E5E7; border-radius:10px; padding:12px 14px; margin-bottom:6px; cursor:pointer; }
.sk-card:hover { border-color:#D0D0D5; box-shadow:0 1px 4px rgba(0,0,0,0.04); }
.sk-detail-overlay { position:fixed; top:0; right:0; bottom:0; width:440px; background:#fff; box-shadow:-4px 0 24px rgba(0,0,0,0.08); z-index:200; padding:28px; overflow-y:auto; }
.sk-detail-overlay.open { display:block; }
.sk-detail-backdrop { position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.2); z-index:199; }
```

## Detail Overlay HTML

Rendered statically in `dashboard_template.py` (not injected by JS):

```html
<div class="sk-detail-backdrop" id="skBackdrop" onclick="closeSkillDetail()"></div>
<div class="sk-detail-overlay" id="skDetailOverlay">
  <button class="sk-detail-close" onclick="closeSkillDetail()">✕</button>
  <div class="sk-detail-cat" id="skDetailCat">proposition</div>
  <div class="sk-detail-key" id="skDetailKey">logistics_segment</div>
  <div class="sk-detail-val" id="skDetailVal">Value here</div>
  <div class="sk-detail-meta">
    <div>📎 Source: <strong id="skDetailSource">Induction</strong></div>
    <div>🕐 Learned: <strong id="skDetailTime">Today</strong></div>
  </div>
  <div class="sk-detail-related" id="skDetailRelated">
    <h4>Related Skills</h4>
    <div id="skDetailRelatedList"></div>
  </div>
</div>
```

## Pitfalls (v2-specific)

- **Cache buster**: After changing `renderLearnings()` in `dashboard.js`, bump the `?v=N` query param in `dashboard_template.py`'s script tag. The browser caches JS aggressively — without the version bump, users see the old UI.
- **Skills limit**: The fetch uses `limit=150`. If skills exceed this, some are hidden. Increase the limit if the tenant's skill count approaches the threshold.
- **No per-category show-more**: v2 shows ALL skills in a category, not just the first 6 like v1 did. This works for 100-150 skills but would need pagination at 500+.
- **Category order is hardcoded**: The `catOrder` array in `buildSkillsHtml()` and the TabSkills section both hardcode the display order. New categories must be added to both arrays.
- **`_skSource` / `_skSearch` globals**: These are module-level globals that persist across navigation. If the user navigates away and comes back, `renderLearnings()` re-runs and resets them via `var _skSource = 'all'` at the top. This is fine because `renderLearnings()` re-initializes them.
- **Two source tabs structs**: Source filter tabs are rendered in the Skills tab HTML inside the page, NOT in `buildSkillsHtml()`. If a future refactor pulls them into a separate function, ensure the click handlers still reference the global `_skSource`/`_skSearch` variables.
- **Category overlap**: Some skills may have multiple valid categories (e.g. a proposition skill could also be a GTM learning). The `category` field is set at creation time and is authoritative. No cross-category dedup is performed.
- **No empty-state per source**: When filtering to a source that has no skills (e.g. "Conversations" on day 1), the empty state "No skills match your filter. Try a different source or search." shows. This is shared with the search-empty state.
