---
name: ara-crm-feature-build
category: productivity
description: Design-first workflow for building CRM pipeline features in ARA — Deals, Activities, pipeline stages, org-level rollups, and human-in-the-loop actions
---

# ARA CRM Feature Build

Build new CRM features in the ARA dashboard (deals pipeline, activities timeline, action items, org management) using a **design-first** approach.

## Foundational Rule: Tenant-First Architecture

Every feature, API endpoint, data model addition, and configuration change MUST be tenant-specific. No tenant name, company name, industry term, or segment keyword should be hardcoded in code.

**Checklist before writing any code:**
- Does this add or change a data model column? → It needs `tenant_id` or lives in `tenant.config` JSON.
- Does this define a keyword, pattern, or mapping list? → It must live in `tenant.config["segments"]` or a tenant-configurable table, not in a Python dict.
- Does this filter or classify data? → The filter rules come from the tenant's config, not from hardcoded arrays.
- Is a company name, industry, or competitor name mentioned? → It must be in tenant config, not in code. Code reads from config at runtime.
- Does this URL, label, or display string reference a specific business vertical? → Must be tenant-configurable.

**Pattern:** Store per-tenant configuration in `tenant.config` (a JSON column). Define API endpoints as `GET/PUT /api/tenants/{tenant_id}/segments`. New lead data (segment, etc.) is auto-assigned by reading tenant config, not hardcoded company lists.

**Exception:** Truly platform-level features (cross-tenant analytics, billing, central agent triage) that have no per-tenant behavior.

## Prerequisites

- ARA server running at `http://localhost:8766`
- `venv/` activated in `/Users/greg/ara/`
- `database.py` has all current models (Tenant, Lead, Conversation, Deal, DealEvent, ActionItem, etc.)
- To wire any new API as an Ava-callable tool, see `references/ava-tool-calling-architecture.md`

## Workflow

### Phase 1: Design Q&A + Mockup (Mandatory — Never Skip)

**For cadence/stage-logic features,** also ask the questions from `references/cadence-logic-design.md` §"Design Questions to Ask Before Building Cadence Logic" — these cover qualification criteria, disqualification, channel switching, dormant thresholds, human notification, and meeting booking flow.

Before writing ANY code, you MUST be 100% clear. Greg's rule: *'Any further questions for me? You should be 100% clear before you write a line of code as a rule.'*

Ask clarifying questions until the design is unambiguous. Do not proceed to code if you still have open questions about the scope, edge cases, or adjacencies that might be affected.

**After Q&A — show a visual mockup before writing any production code.** Greg's explicit preference (confirmed in cadence builder and threads layout): he wants to see and approve the layout before you build it.

Workflow:
1. Write a standalone HTML mockup to `file:///Users/greg/hermes-sketch/<feature-name>.html`
2. Present it via `browser_navigate('file:///Users/greg/hermes-sketch/<feature-name>.html')`
3. Use `browser_vision()` to get visual feedback on layout, spacing, alignment
4. Iterate with Greg on the mockup: move elements, change spacing, adjust proportions
5. Only start building production code after Greg explicitly approves the layout

The mockup should include real-looking sample content (lead names, company names, avatars) so Greg can evaluate the visual balance. Use the ARA color palette (light gray sidebar, white cards, Inter font, subtle borders).

**Corollary: never build layout changes from verbal description alone.** If Greg describes a layout change, say 'Let me mock that up so you can see it' and produce a standalone HTML file first.

For pipeline/CRM features, these questions are the right starting point:

1. **Org vs individual:** Are deals at the company level (multiple leads → one deal) or per-lead?
2. **Trigger:** When does a deal get created? (Manual only? Auto on stage promotion? Both?)
3. **Pipeline stages:** What stages make sense? (Greg's current: New → Reached Out → Engaged → Qualified → Meeting Booked → Won/Lost/Dormant)
4. **Deal value:** Manual entry? Auto-calculated? Notes for calculation?
5. **Dashboard metrics:** What stats matter? (Greg tracks: Deals in Pipeline, Meetings Booked, Deals Closed)
6. **Activities scope:** At lead level, deal level, or both?
7. **Human-in-loop:** Where does the human need to intervene? Ava can suggest, human confirms.

### Phase 2: DB Models

1. Create new SQLAlchemy models in `database.py`:
   - `id` = `Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])`
   - `tenant_id` = FK to tenants
   - `created_at` / `updated_at` with `utcnow()`
   - Add FKs and relationships between new and existing models
2. Add new model imports to `server.py`
3. Create tables: run `Base.metadata.create_all()` or ALTER TABLE for existing tables
4. For ALTER TABLE on SQLite: use raw SQL `ALTER TABLE leads ADD COLUMN deal_id VARCHAR REFERENCES deals(id)`

### Phase 3: API Endpoints

Add endpoints to `server.py`. Follow these patterns:

- **Serialization helper**: `_serialize_deal(d, db)` — keeps response format consistent
- **Route ordering**: Static routes (`/api/deals/stats`) BEFORE parameterized routes (`/api/deals/{deal_id}`)
- **CRUD**: List, Get, Create, Update. PATCH with event logging for state changes
- **Sub-resources**: `POST /api/deals/{id}/attach-lead` — separate endpoints for relationships
- **Cascade DELETE**: When deleting a parent entity with foreign-key relationships, unlink or delete children first to maintain referential integrity:
  ```python
  @app.delete("/api/deals/{deal_id}")
  def delete_deal(deal_id: str, db: DBSession = Depends(get_db)):
      deal = db.query(Deal).filter(Deal.id == deal_id).first()
      if not deal: raise HTTPException(404)
      # Step 1: Unlink child records (set FK to NULL)
      for lead in db.query(Lead).filter(Lead.deal_id == deal_id).all():
          lead.deal_id = None
      # Step 2: Delete child/event records
      db.query(DealEvent).filter(DealEvent.deal_id == deal_id).delete()
      # Step 3: Delete the parent
      db.delete(deal)
      db.commit()
      return {"ok": True, "deleted": deal_id}
  ```
  **Cascade order:** unlink (set NULL) → delete child records → delete parent. This avoids FK constraint violations.
- **Stats**: `GET /api/deals/stats` — aggregations the dashboard needs
- **TIMEOUT route**: In `PATCH` handlers, add `timeout` param for async event recording: `ForkEvent(DealStageChange(..., timeout=...)` — ensures changes are logged even if the request takes time
- **Event logging**: Every meaningful state change (stage, value, lead attach/detach) creates a `DealEvent` record
- **Clean import lines**: Keep `from database import ...` lines under 120 chars, use backslash or multiple lines if needed

### Phase 4: Frontend — Standalone JS (preferred) or Dashboard Template

**As of May 2026, ARA uses standalone `static/dashboard.js`** (not inline JS in Python templates). This was migrated because Python triple-quoted strings caused persistent JS escaping bugs.

#### Architecture Decision: Standalone JS vs Python-Embedded JS

| Factor | Standalone `static/dashboard.js` | Python-embedded (`dashboard_template.py`) |
|--------|------|------|
| JS escaping bugs | None | Constant (backslash doubling, `\\n` absorption, quote hell) |
| Tooling | `node --check`, ES Lint, prettier | None — can't run standard JS tooling |
| Debugging | Browser DevTools with source maps | Raw `<script>` block, line numbers don't match |
| Deployment | One file to update | Requires server restart to re-render template |
| **Recommended** | ✅ **Always prefer this** | ❌ Only for legacy pages |

**How the standalone JS loads:** The Python template (`dashboard_template.py`) serves the HTML shell and imports the JS via `<script src="/static/dashboard.js"></script>`. The FastAPI server mounts it via `static_files = StaticFiles(directory="static")` and `app.mount("/static", static_files, name="static")`.

**How to add features:**
1. Find the relevant function in `static/dashboard.js` (e.g., `renderDeals()`, `showLeadDetail()`)
2. Add/modify the HTML string-building there
3. Validate with `node --check static/dashboard.js`
4. Reload the browser page (no server restart needed — the JS is served directly, not rendered through a template)

#### Legacy pages still using Python-embedded JS:

For pages still in `dashboard_template.py`, the old patterns apply (see escaping pitfalls below). But migrate new features to standalone JS when possible.

#### Adding a new page:

1. **Sidebar**: Add `onclick="showPage('pagename')"` to the nav item
2. **showPage()**: Add `else if (page === 'pagename') renderPageName();`
3. **render function**: Async function that fetches from API and generates HTML

#### Standalone Pages (Full-page routes outside the SPA)

When building a standalone page served from its own route (`/cadence`, not an SPA page inside `#centerPanel`), you MUST include the dashboard's app shell:

1. **Sidebar** — identical nav items as `dashboard_template.py`. Same structure, same header/footer. Use `window.location='...'` for nav links since there's no SPA routing.
2. **Ava Chat Panel — DATA SCREENS ONLY** — identical HTML structure, CSS classes, and JS functions (`TENANT`, `activeThreadId`, `sendChatMsg`, `loadActiveThreadMessages`, `addChatMsg`, etc.). The chat panel is part of the app shell **only on data screens** where the user works with live records alongside Ava.

   **Exception — config screens:** Do NOT include the chat panel on configuration pages (Cadences, Integrations, Settings, or any page where the user configures automation rules rather than viewing/managing leads, deals, or reports). On these pages, the layout is:
   - `[sidebar 240px] [content-area flex:1]` — no chat panel
   - Secondary panels (conditions, filters, metadata) go inside the content area as a right-aligned column

   **Rule of thumb:** If the page exists to configure *how* the system works (Cadences = outreach rules, Integrations = credentials, Settings = preferences), skip the chat. If the page exists to *work with* data (Dashboard = metrics, Leads = records, Deals = pipeline), include it.

   This is a Greg-specific design convention — confirmed explicitly after it was built wrong and corrected.

   See `references/cadence-builder-v2-architecture.md` for the v1 Cadence Builder and `references/cadence-builder-v2-architecture.md` for the v2 (objective-led, brand voice system, LLM-powered preview, per-template state with localStorage, clickable step cards with inline delay editing). See `references/cadence-builder-v3-structured-fields.md` for the v3 structured fields pattern. See `references/cadence-v4-frontend-patterns.md` for v4 (single textarea per step, channel prompts merged into desc, SMS removed, system prompt persistence fix, unsaved changes warning, sidebar consistency between pages). See `references/drag-drop-reorder-steps.md` for HTML5 drag-drop reorder implementation.
3. **Layout structure — two patterns depending on page type:**

   **Pattern A — Data screens (with chat panel):**
   - `[sidebar 240px] [content-area flex:1] [chat-panel 380px]`
   - Use `.content-wrap { flex: 1; display: flex; overflow: hidden; }` inside `.main`
   - Use `.content-left { flex: 1; overflow-y: auto; }` for main content
   - Secondary panels go INSIDE `.content-wrap` as right-aligned column, not as additional top-level columns

   **Pattern B — Config screens (no chat panel):**
   - `[sidebar 240px] [content-wrap flex:1, scrollable]`
   - Use `.content-wrap { flex: 1; overflow-y: auto; }` — single scrollable column
   - For internal 50-50 splits, use `.body-split` inside content-wrap:
     ```css
     .body-split { display: flex; gap: 36px; }
     .left-col { flex: 1; min-width: 0; }
     .right-col { flex: 1; min-width: 0; }
     ```
   - Horizontal layout elements (mapping strips, template cards) go above the split at full width
   - Conditions and secondary cards go inside `.right-col`, side-by-side via `.cond-inline`:
     ```css
     .cond-inline { display: flex; gap: 16px; }
     .cond-inline .cond-card { flex: 1; }
     ```
   - The Cadence Builder page (`/cadence`) is the canonical reference for Pattern B
4. **Copy the full chat JS** — `getStoredThread`, `setStoredThread`, `sendChatMsg`, `startNewChat`, `loadActiveThreadMessages`, etc. These are not shared code — each standalone page carries its own copy.

**Pitfall — never skip UI chrome:** A standalone page without the sidebar or chat panel will be corrected. The sidebar + chat panel are the app shell. Every page shares them.

Key patterns for ARA's JS-in-Python-string architecture:

```javascript
// ⚠️ ESCAPING — triple-quoted Python strings eat backslashes
// In Python """...""", \\\\' produces \\' in the JS output
// Use template literals (backticks) to avoid escaping hell:
html += `<button onclick="fn('${id}')">Click</button>`;

// For modal/overlays, use insertAdjacentHTML + event.stopPropagation():
var modal = '<div style="position:fixed..." onclick="this.remove()">' +
  '<div onclick="event.stopPropagation()">...' +
'</div></div>';
document.body.insertAdjacentHTML('beforeend', modal);
```

#### Pipeline View (Deals kanban grid):

**Two-tier layout:** Pipeline stages (5 columns) + Terminal stages (3 columns below).

```javascript
// 5 pipeline columns + 3 terminal columns below
var stages = ['new', 'reached_out', 'engaged', 'qualified', 'meeting_booked', 'deal_won', 'lost', 'dormant'];
var stageLabels = {'new':'New','reached_out':'Reached Out','engaged':'Engaged','qualified':'Qualified','meeting_booked':'Meeting Booked','deal_won':'Won','lost':'Lost','dormant':'Dormant'};
// Render two grids:
//   1) 5-column grid for pipeline stages: new → reached_out → engaged → qualified → meeting_booked
//   2) 3-column grid below for terminal stages: deal_won | lost | dormant
// Each column is a card stack with dropzone for HTML5 drag-and-drop
// Cards show: org_name, contact_name + designation, lead_count, expected_value (₹), industry_segment
// Empty columns: "No deals" placeholder + "+ Add Deal" button
// Drag-and-drop: optimistic DOM move first, PATCH /api/deals/{id} with {stage: targetStage} on background
```

#### Add Deal Modal (Replaces old inline form)

The inline form approach was replaced with a **modal popup** (same pattern as Edit). Clicking "+ Add Deal" now opens a polished modal:

```javascript
function showAddDealModal(stage) {
  if (document.querySelector('.modal-overlay')) return; // Prevent double modals
  // Build modal HTML with all deal fields in organized rows:
  // Row 1: Organization Name (required, full width, marked with *)
  // Row 2: Contact Person | Designation
  // Row 3: Email | Phone
  // Row 4: Stage (pre-selected to column clicked) | Industry (dropdown)
  // Row 5: Source Channel (dropdown) | Expected Value
  // Row 6: Notes
  // Footer: Create Deal + Cancel buttons
}
```

**Key design choices:**
- **Stage pre-filled** from `data-stage` attribute on the "+" button — the column determines starting stage
- **One create point** — all fields in one modal, not a cramped inline form
- **Lead auto-creation** — contact name/email/phone auto-create a linked Lead with duplicate lookup (by phone, then email)
- **Cancel + overlay click** close the modal
- **"Creating..."** state on submit button, disabled during API call
- **Re-render** on success: `renderDeals()`
- **"Organization Name *"** label marks the only required field (backend also validates stage)

**Event handler (inside the modal's direct listener, not delegation):**
```javascript
// Inside the modal's click handler:
if (a === 'create-deal') { createDealFromModal(); }
```

**The `createDealFromModal()` function:**
1. Reads all field values from modal inputs
2. Strips empty strings (sends `undefined` → deleted from body)
3. Sets `deal_owner` to "Ava"
4. POSTs to `/api/deals` with all fields
5. On success: checks `_dealLeadAttach` — if set, auto-attaches the new deal to that lead and shows the lead detail page; otherwise removes all modals + calls `renderDeals()`
6. On failure: re-enables button, shows alert

**Leads page flow:** `_dealLeadAttach = null` → normal behavior (navigates to Deals page)
**Lead detail flow:** `_dealLeadAttach = leadId` → auto-attach + stay on lead detail

**Why modal > inline form:** Modals avoid cramped column layouts, scale better with 10+ fields, work on mobile, and look professional. The inline form was replaced after user feedback that it was "ugly."

The pipeline column now only renders:
```javascript
html += '<button data-action="add-deal" data-stage="' + s + '" class="add-deal-btn">+ Add Deal</button>';
```
No hidden inline form, no per-column form IDs, no cancel-add-deal or submit-add-deal handlers in delegation.

#### Deal Detail pattern (Edit button + Three-Dot Menu + Deal Journey Timeline):
- Breadcrumb: Deals > Org Name
- Header with org name + **"Edit"** button (NOT separate Move Stage + Edit Value buttons) + **three-dot (⋮) menu** for additional actions
- **Deal Journey Timeline** — horizontal pipeline below header, replaces Status section
  - ALL 5 stages shown for every deal (Reachout → Qualified → Meeting Booked → Closed Won → Churned)
  - Completed + Current: green gradient (`#059669 → #10b981`). No color distinction — current is distinguished via shadow+scale+higher z-index
  - Future stages: gray `#F3F4F6` with `#9A9A9E` text, duration `—`
  - Time-in-stage displayed per block (real duration from events, or `—` for skipped/never-visited stages)
  - Arrow connectors between blocks matching preceding segment's color
  - Hover tooltips show entered_at, exited_at, duration (CSS-only hover, no JS). Stages never visited have `entered_at: null` so tooltip doesn't render.
  - `formatDuration()` safely handles `0`/`null` → returns `—`
  - "Current Stage: X" label below timeline plus stuck warning when >14 days
  - See `references/deal-journey-timeline.md` for full implementation
- **Sections-based info layout** (replaces generic 3-column card):  
  - **Contact Person**: name, designation, email (blue link), phone  
  - **Expected Value**: formatted in ₹, notes below  
  - **Details**: Industry, Source, Owner, Domain (lead-info-row pattern)  
  - **Leads (N)**: clickable link list → opens lead detail page  
  - Each section uses `lead-detail-section` class with staggered left padding to visually separate them
- **Activity Timeline** below — events from `DealEvent` records

#### Three-Dot Menu (⋮) Pattern (Detail Page + Toolbar)

Use a three-dot menu for secondary actions both on detail pages and toolbar-level bulk operations.

**Detail page** — next to the Edit button for per-record actions:
```javascript
html += '<div style="position:relative;display:inline-block;">';
html += '<button class="deal-dots-btn" onclick="toggleDealMenu(event)">⋮</button>';
html += '<div id="dealMenu" class="deal-menu-dropdown" style="display:none;position:absolute;...">';
html += '<div class="deal-menu-item disabled">🔁 Merge Deal</div>';
html += '<div class="deal-menu-item" onclick="deleteDeal()">🗑 Delete Deal</div>';
html += '</div></div>';
```

**Toolbar** — in the right-aligned button group for bulk actions (⋮ goes on the absolute right):\n```\n[👤 Assign ▼] [+ Add Lead] [⋮]\n```
The toolbar two-dropdown pattern requires:
- Each dropdown in its own `position:relative` wrapper
- `closeLeadsDropdowns()` called before opening any dropdown
- An outside-click handler that checks both wrappers via `!target.closest()`

```javascript
// Add to the deal detail header, next to the Edit button:
html += '<div style="position:relative;display:inline-block;">';
html += '<button class="deal-dots-btn" onclick="toggleDealMenu(event)">⋮</button>';
html += '<div id="dealMenu" class="deal-menu-dropdown" style="display:none;position:absolute;...">';
html += '<div class="deal-menu-item disabled" style="color:#999;cursor:not-allowed;">🔁 Merge Deal</div>';
html += '<div class="deal-menu-item" onclick="deleteDeal()">🗑 Delete Deal</div>';
html += '</div></div>';
```

**Key design decisions:**
- **Position:relative** on the parent container so the dropdown positions absolutely relative to the button
- **Click-outside handler** to close — add to a shared `document.addEventListener('click', function...)` that checks `!target.closest('.deal-dots-btn') && !target.closest('#dealMenu')`
- **Disabled items** use `cursor:not-allowed` + muted color (`#999`), no onclick handler
- **Destructive actions** (Delete) use a `confirm()` dialog before making the API call
- **Menu items** use `padding:8px 16px` with hover backgrounds for interactive feel

```javascript
function toggleDealMenu(event) {
  event.stopPropagation();
  var menu = document.getElementById('dealMenu');
  menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
}

function deleteDeal() {
  if (!confirm('Are you sure you want to delete "' + currentDealOrg + '" and all its data?')) return;
  fetch('/api/deals/' + currentDealId, { method: 'DELETE' })
    .then(r => r.json())
    .then(function() { showPage('deals'); });
}
```

**Pitfalls:**
- `event.stopPropagation()` on the toggle button prevents the document-level click handler from immediately closing the menu you just opened
- The document-level close handler must check `!target.closest('#dealMenu')` in addition to checking the button — otherwise clicking inside the menu closes it
- Use `getElementById` for the menu (not class or querySelector) to avoid DOM stales when re-rendering the detail page

#### Modal patterns (stage change, value edit, attach lead, add deal):
- Create overlay div with `position:fixed; inset:0; background:rgba(...); z-index:1000; backdrop-filter:blur(2px)`
- Inner card with `data-action="stop-propagation"` to prevent close on click-inner
- Buttons call async functions via direct event listener on the overlay, or via delegation if modal is inside #centerPanel
- Remove modal: `document.querySelectorAll('.modal-overlay').forEach(m => m.remove())` — use class selector, NOT fragile `[style*="position:fixed"]` which is unreliable

**Modal event listener pattern (for body-inserted modals):**
```javascript
// Modals inserted into document.body need their OWN click listener
// because the event delegation on #centerPanel won't catch them
var overlay = document.body.lastElementChild;
if (overlay && overlay.classList.contains('modal-overlay')) {
  overlay.addEventListener('click', function(e) {
    var a = e.target.getAttribute && e.target.getAttribute('data-action');
    if (a === 'close-modal') { overlay.remove(); }
    else if (a === 'stop-propagation') { e.stopPropagation(); }
    else if (a === 'action-name') { handleAction(); }
  });
}
```

For modals built with `document.createElement` + `appendChild`, attach the listener directly to the modal element. For modals built with `insertAdjacentHTML`, find the newly created overlay via `document.body.lastElementChild` (assumes it's the last child).

### Deal Enrichment Pattern (Adding Fields to Existing Model)

When expanding a deal (or any CRM entity) with new fields, use this layered approach:

**Layer 1 — DB Schema (database.py):**
```python
# Add columns to the existing model
contact_name = Column(String)
contact_email = Column(String)
contact_designation = Column(String)
contact_phone = Column(String)
industry_segment = Column(String)
source_channel = Column(String)
deal_owner = Column(String, default="Ava")
```

**Layer 2 — Migration (server.py lifespan):**
```python
# Use raw SQL ALTER TABLE — SQLite doesn't auto-add columns
deal_cols = [c['name'] for c in inspector.get_columns('deals')]
deal_migrations = {
    'contact_name': "ALTER TABLE deals ADD COLUMN contact_name VARCHAR",
    'contact_email': "ALTER TABLE deals ADD COLUMN contact_email VARCHAR",
    # ... one per new field
}
for col_name, sql in deal_migrations.items():
    if col_name not in deal_cols:
        db_session.execute(sa_text(sql))
db_session.commit()
```

**Layer 3 — Serialization + API (server.py):**
- Add each new field to `_serialize_deal()` return dict, with fallback to empty string
- Add each to `create_deal()` by reading from `data.get("field", "")`
- Add each to `update_deal()` by checking `if "field" in data` and `setattr(d, field, data[field])`
- Update deal events: log changes only when values actually differ

**Layer 4 — Frontend (dashboard.js):**
- Deal cards in pipeline: add rows for contact_name, industry_segment
- Deal detail page: restructure sections to show new grouped fields
- Edit modal: include all fields in clean 2-column row layout
- Add Deal modal: include new contact fields + industry + source dropdowns

**The Lead Auto-Creation/Lookup Pattern:**

When creating a deal with contact info (name, phone, email), the backend should:
1. **Normalize** contact_email to lowercase, strip phone
2. **Lookup by phone** — if an existing lead matches by phone AND is unassigned to another deal, link it
3. **Lookup by email** — if phone didn't match, try email
4. **If neither matches and contact info exists** — auto-create a new Lead:
   ```python
   lead = Lead(
       tenant_id=tenant.id,
       name=deal.contact_name or deal.org_name,
       email=deal.contact_email,
       phone=deal.contact_phone,
       company=deal.org_name,
       lead_source=deal.source_channel or "deal",
       stage="new",
       deal_id=deal.id,
   )
   db.add(lead)
   ```
5. **If matched but unassigned** — link by setting `lead.deal_id = deal.id`
6. **Log** a `DealEvent` for the lead attachment

The frontend passes contact fields from the Add Deal form; the backend handles all the lead logic.

### Unified "Edit" Button Pattern

**Do NOT** use separate "Move Stage" + "Edit Value" + "Edit Contact" buttons. Replace them with a single **"Edit"** button that opens a modal with ALL deal fields:

```javascript
function editDeal(dealId) {
  // Build modal with all fields in organized rows:
  // Row 1: Organization Name (full width)
  // Row 2: Contact Name | Designation
  // Row 3: Email | Phone
  // Row 4: Stage (dropdown) | Industry (dropdown)
  // Row 5: Source Channel (dropdown) | Owner
  // Row 6: Expected Value
  // Row 7: Notes / Calculation (textarea)
  // Row 8: Save | Cancel

  // Populate current values by reading sections from the rendered page DOM
  // (not a separate API call — the data is already on screen)
}
```

**Key design principles:**
- **One edit point** for all deal fields — users don't need to remember which button opens which field
- **Pre-populated** from the DOM so the user sees current values before editing
- **Dropdowns for controlled vocabularies** (stage, industry, source) — free-text for contact info
- **Clean 2-column layout** using `display:flex;gap:8px` inside the modal
- Save sends ALL fields via PATCH (undefined values are stripped client-side)

### Button Audit Methodology

Before declaring any UI build "done", run a systematic button audit:

1. **Extract all `data-action` values:**
   ```bash
   grep -o 'data-action="[^"]*"' static/dashboard.js | sort -u
   ```

2. **Find the event delegation section** (look for `// Event delegation` and `addEventListener('click'`)

3. **Extract all handled actions** from the delegation switch (`if (action === '...')` branches)

4. **Cross-reference** — any `data-action` NOT in the handler list is a dead button

5. **Check separate event listeners** — `<select>` dropdowns use `document.addEventListener('change', ...)` with `closest('[data-action="change-cadence"]')` — these won't appear in click delegation

6. **Check direct modal listeners** — body-inserted modals use `overlay.addEventListener('click', ...)` — their handlers bypass delegation entirely

7. **Validate JS syntax:** `node -c static/dashboard.js`

This catches dead "More" buttons, missing Cancel handlers, and unhandled dropdown actions.

**Key fix patterns discovered during audits:**
- **Deal card clicks:** Use `e.target.closest('.deal-card')` (not `e.target.classList.contains('deal-card')`) — the `closest()` approach catches clicks on child elements inside the card (labels, spans, divs), while `contains()` only triggers if the exact click target has the class
- **Modal Cancel buttons:** If a modal is appended to `document.body` (outside `#centerPanel`), its Cancel button won't be caught by the event delegation handler on `#centerPanel`. Add a direct event listener on the modal overlay instead
- **Add Deal button:** Now calls `showAddDealModal(stage)` (not inline form reveal) — update the delegation handler accordingly

### Alternative: Two Buttons with Redundant Entry Point

See `references/deal-enrichment.md` for the full enrichment implementation with lead auto-creation and migration workflow.

### Lead Archive (Soft-Delete-via-Stage) Pattern

When the user asks for "delete" but means "remove from active view without losing data," use a **soft archive via stage** rather than hard-delete. This preserves conversations, deals, action items, and chat history.

#### Design Decisions

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| Storage | `stage='archived'` (not a new column) | Reuses existing stage field; no migration needed; schema stays clean |
| Cascade | **No cascade** — conversations, deals, action items stay intact | User may reactivate → needs full history |
| Data permanence | All relationships preserved | Archived lead is just a lead with a different stage |
| Restoration | Change `stage` back to previous value (e.g. `reached_out`) | Simple PATCH; no special unarchive API needed |

#### Backend: Archive Instead of Delete

```python
# In bulk_delete endpoint — overwrite, don't cascade
@app.post("/api/leads/bulk-delete")
def bulk_delete_leads(data: dict, db: DBSession = Depends(get_db)):
    lead_ids = data.get("lead_ids", [])
    archived = 0
    for lid in lead_ids:
        l = db.query(Lead).filter(Lead.id == lid).first()
        if l:
            l.stage = "archived"
            l.updated_at = utcnow()
            # Cancel pending scheduled actions
            db.query(ScheduledAction).filter(
                ScheduledAction.lead_id == lid,
                ScheduledAction.status.in_(["pending", "firing"])
            ).update({"status": "cancelled"})
            archived += 1
    db.commit()
    return {"ok": True, "archived": archived}
```

#### Backend: Block Tools for Archived Leads

Every outbound tool (send_whatsapp, send_email, trigger_cadence, schedule_message, schedule_email) must check the lead's stage before proceeding:

```python
def _check_archived(lead, tool_name):
    if lead.stage == "archived":
        return {"error": f"Cannot {tool_name}: {lead.name} is archived. Reactivate the lead first."}
    return None

# Inside execute_tool:
archived_check = _check_archived(lead, "send WhatsApp")
if archived_check: return archived_check
```

**Tools to guard:** `send_whatsapp`, `send_email`, `trigger_cadence`, `schedule_message`, `schedule_email`. Each should return a clear, actionable error message.

#### Backend: Filter Archived from Listings

When the user or Ava queries leads without explicitly asking for archived ones, exclude them:

```python
# In list_leads, search_leads, and the system prompt's leads query:
query = query.filter(Lead.stage != "archived")

# Optional: add an `include_archived` parameter for admin tools
def resolve_lead(...):
    # When called from user-facing endpoint, exclude archived
    if not data.get("include_archived"):
        leads = db.query(Lead).filter(Lead.id.in_(lead_ids), Lead.stage != "archived").all()
```

#### System Prompt: Instructions for Ava

Add a HARD RULE section in the system prompt's Guidelines:

```
**Archived leads:** Leads with stage "archived" are NOT active. 
- Do NOT send them WhatsApp messages, emails, or trigger cadences
- Do NOT include them in lead counts or pipeline numbers
- Do NOT attempt to engage with them
- If the user asks about an archived lead, explain it's archived and offer to reactivate
```

#### Frontend: Archive Button Instead of Delete

```javascript
// In the bulk actions dropdown or three-dot menu:
async function bulkArchiveLeads() {
  closeLeadsDropdowns();
  var ids = getSelectedLeadIds();
  if (ids.length === 0) { alert('Select leads first'); return; }
  if (!await confirm('Archive ' + ids.length + ' lead' + (ids.length > 1 ? 's' : '') + '? Archived leads can be restored later.')) return;
  var r = await fetch('/api/leads/bulk-delete', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ lead_ids: ids })
  });
  if (!r.ok) { alert('Failed to archive leads'); return; }
  renderLeads();
}
```

**Key frontend differences from delete:**
- Button text: "🗑 Archive" (not "🗑 Delete")
- Confirm message: says "can be restored later" instead of "cannot be undone"
- No modal for individual archive — uses same bulk endpoint with single ID

#### Verification

1. Archive a lead → `{"ok": True, "archived": 1}` ✓
2. List leads → archived lead does NOT appear ✓
3. Search leads → archived lead does NOT appear ✓
4. Try send_whatsapp → `"Cannot send WhatsApp: {name} is archived. Reactivate first."` ✓
5. Restore lead → PATCH `stage` back → lead reappears in listings ✓
6. Verify DB directly: `sqlite3 ara.db "SELECT name, stage FROM leads WHERE stage='archived';"` — confirm data preserved

#### Pitfalls

- **Archive is NOT hard-delete**: Don't cascade-delete conversations, deals, or action items. The archive is reversible.
- **Security allowlist still applies**: Archived leads' phone numbers are still valid destinations for outbound security purposes — the archive block is an additional layer, not a replacement for destination validation.
- **Restoration is manual**: There's no "unarchive" API by default — PATCH the lead's stage back to a previous value. If users need a UI for this, add an "Archived" filter/ tab in the leads page.
- **Scheduled actions must be cancelled**: Archived leads should not have pending cadence steps fire. Cancel all pending actions on archive.

### Pipeline Stage Refactoring

When stage names change (migration, reordering, rename), the full refactor touches 7 layers: DB model → migration → API hooks → serialization → timeline → JS kanban → JS dropdowns. See `references/pipeline-stage-refactor.md` for the complete step-by-step with grep patterns, migration SQL, and the auto-dormant/auto-sync patterns.

## Phase 5: Verification

1. **API test**: curl each new endpoint — create, read, update, attach, stats
2. **Verify DB state directly after every tool-based API call**: Every API endpoint's self-report is a promise. Verify it with a SELECT query before moving on. The most common failure mode is "API returned 200 but data didn't persist" (wrong column, constraint violation, silent rollback). A single `venv/bin/python -c "import sqlite3; print(sqlite3.connect('ara.db').execute('SELECT city FROM leads WHERE name LIKE ?', ('%Gregory%',)).fetchone())"` catches this before the user ever sees a stale UI.
3. **Frontend test**: Load dashboard, click into each new page, verify no JS errors
3. **Adjacent component testing** (do this after EVERY bug fix): Identify all surfaces that touch the changed code path. For example, if you fix a bug in `agent_chat()`, test:
   - First message (new thread) ✅
   - Follow-up messages (existing thread) ✅
   - Thread list API (updated timestamps accurate)
   - Thread detail API (messages loaded correctly)
   - Dashboard chat panel (loads latest thread on refresh)
   - Thread persistence (localStorage 12h TTL still works)
   Explicitly list what you tested and what you didn't. Report the full matrix.
4. **State persistence**: Create a deal, attach a lead, change stage — refresh page, verify data persists
5. **Edge cases**: Empty pipeline, detach last lead, change to/from every stage

## Phase 6: Time-Based Actions & Scheduler Daemon

For features that execute actions at scheduled times (follow-up messages, call reminders, automated emails), use this pattern.

### DB Model

```python
class ScheduledAction(Base):
    __tablename__ = "scheduled_actions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True)
    action_type = Column(String, nullable=False)  # whatsapp, email, call_reminder, internal_note
    status = Column(String, default="pending")  # pending, firing, completed, failed, cancelled
    scheduled_at = Column(DateTime, nullable=False)
    fired_at = Column(DateTime, nullable=True)
    payload = Column(JSON, default=dict)
    channel = Column(String, default="whatsapp")
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    last_error = Column(Text, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)
```

Add migration in server.py lifespan using raw SQL for SQLite.

### Scheduler Daemon

Background thread polling every 30s, started in lifespan. Fetch due actions (scheduled_at <= now, status=pending/firing) AND retry-eligible actions. Mark as "firing" before executing. On success: "completed" + fired_at. On failure: increment retry_count, apply exponential backoff (60s → 300s → 900s), set next_retry_at. On permanent failure: create LearningNotification to alert human.

### Execution Channels

WhatsApp: `wa.send(lead.phone, payload.message)`. Email: `send_via_gmail_api()`. Call reminder / internal note: creates LearningNotification.

### Auto-Cancellation on Re-Engagement

When inbound message arrives from a lead with pending/firing actions, cancel them all. Ava then asks if they want to reschedule.

### Auto-Dormant Detection

Background daemon checks leads with active stages for 30-day inactivity:
```python
def _check_dormant():
    """Mark leads and deals as dormant if 30 days since last activity."""
    cutoff = utcnow() - timedelta(days=30)
    for lead in db.query(Lead).filter(Lead.stage.notin_(["dormant"])):
        last_conv = db.query(Conversation).filter(
            Conversation.lead_id == lead.id
        ).order_by(Conversation.created_at.desc()).first()
        if last_conv and last_conv.created_at < cutoff:
            lead.stage = "dormant"
        elif not last_conv and lead.created_at < cutoff:
            lead.stage = "dormant"
    # Deals follow: if all attached leads dormant → deal dormant
```
Runs every 30s inside the scheduler loop. Dormant leads re-activate to "engaged" on inbound reply.

### Deal Stage Auto-Sync from Lead

When a lead advances (inbound/outbound/PATCH), sync its deal up to `meeting_booked`:
```python
def _sync_deal_stage_from_lead(lead_id):
    """Push deal stage forward up to meeting_booked when lead advances."""
    stage_order = ["new", "reached_out", "engaged", "qualified", "meeting_booked"]
    lead_idx = stage_order.index(lead.stage) if lead.stage in stage_order else -1
    deal_idx = stage_order.index(deal.stage) if deal.stage in stage_order else -1
    if lead_idx > deal_idx and lead_idx >= 0:
        new_stage = stage_order[min(lead_idx, len(stage_order) - 1)]
        deal.stage = new_stage
        deal.stage_entered_at = utcnow()
        # Log DealEvent
```
Only moves forward, never backward. After `meeting_booked`, stage changes are manual (PATCH/drag-drop).

### API Endpoints

Route ordering: static routes (`/api/actions/stats`) BEFORE parameterized (`/api/actions/{id}`). Create, list (status/lead_id/upcoming filters), stats, detail, cancel one, cancel-all-for-lead.

### Ava Integration

Add to system prompt: detect "call me later" intents, confirm time, POST /api/actions with lead_id/action_type/channel/payload/scheduled_at. Same channel unless lead specifies another.

### Actions Page UI

Timeline grouped by day (Today → Tomorrow → Future). Stats cards. Action cards with type icon, message, lead name, relative time, status badge, cancel button.

### Notification Bell — AHA-Only

Filter bell to only show: `synthesis_ready`, `action_failed`, `call_reminder`, `internal_note`, `action_scheduled`. Hide noisy skill-learning notifs. API supports `?types=type1,type2` parameter.

See `references/scheduled-actions-architecture.md` for full implementation transcript.
See `references/action-notification-engine.md` for the three-channel notification system (WhatsApp + email + platform).

## Phase 7: Cadence Logic Implementation

The stage advancement, channel switching, and meeting booking logic described in `references/cadence-logic-design.md` and `references/cadence-logic-synthesis.md` was **built May 26, 2026**. See `ara-scheduled-actions` skill for implementation details.

### Build Status

| # | Item | Status |
|---|------|--------|
| 1 | `engaged → qualified` — `evaluate_qualification` tool with broad ICP/KB matching | ✅ Built |
| 2 | Disqualification handling — `lost` bucket, cadence exclusion, human notification | ✅ Built |
| 3 | Post-engaged scheduling fix — `engaged`+ excluded from cadence scheduling | ✅ Built |
| 4 | Post-engaged agentic behavior — meeting-nudging in both Ava prompts | ✅ Built |
| 5 | `qualified → meeting_booked` — `mark_meeting_booked` tool, ActionItem notification | ✅ Built |
| 6 | Smart dormant re-engagement — checks deal stage, restores to qualified if applicable | ✅ Built |
| 7 | Channel switching rules — template-silent, email preference, consistent messaging | ✅ In prompts |
| 8 | 7-day silence resume — `_check_silence_resume()` alternating email↔WhatsApp weekly | ✅ Built |
| 9 | Email hook testing | ⏳ Deferred |
| 10 | Calendly / calendar meeting integration | ⏳ Deferred |
| 11 | ActionItems UI (dashboard page with bell badge, resolve/dismiss, Actions/Activities split) | ✅ Built |
| 12 | Per-lead override UI | ⏳ Deferred |

### Key Design Rules to Encode
- **Templates are void after first reply.** Once a lead responds, Ava goes fully agentic toward meeting booking. No template override needed.
- **Consistent messaging across channels** is non-negotiable. Ava must not contradict herself on WhatsApp vs email.
- **Disqualification = `lost` bucket + cadence exclusion.** Ava can remind human the lead opted out if asked to resume. Suggest subtle approach but keep instincts strong — that is the agentic nature.
- **Broad qualification.** Don't disqualify unless a *complete* mismatch. KB + induction are the source of truth.
- **Dormant re-engagement defaults to `engaged`.** Only return to original stage if the lead had a legitimate reason (health, travel, etc.). Trivial reply → `engaged`.
- **Meeting booking is human-coordinated with proactive backup-slot ask.** Ava asks for backup slots *before* human responds. If human silent: "My manager has yet to confirm — apologies — would you have a few more slots?"
- **Post-silence protocol:** 1 email + 1 WhatsApp per week, alternating. Dignified only.
- **Human notification:** ActionItem + LearningNotification for bell. Later: Telegram/WA. Exportable as JSON to CRM.
- **Multi-Ava:** Same logic across all Avas. Cadence is per-lead.
- **Meeting detection:** Content-based ("let's meet Thursday" = meeting_booked). Calendly deferred.

## Lead Management Patterns

### Lead Table Bulk Selection + Actions

When leads need checkbox selection for bulk operations (assign, delete, merge), use this pattern:

**Toolbar layout** — right-aligned action buttons next to left-aligned count:
```javascript
function renderLeads() {
  cp.innerHTML =
    '<div class="page-title">Leads</div>' +
    '<div class="leads-toolbar">' +
      '<span class="leads-count">' + leads.length + ' total</span>' +
      '<div class="leads-toolbar-right">' +
        // Assign button with dropdown
        '<div class="leads-assign-wrap" style="position:relative">' +
          '<button class="leads-assign-btn" onclick="toggleAssignDropdown()"><span class="assign-icon">👤</span> Assign</button>' +
          '<div id="assignDropdown" class="leads-dropdown" style="display:none">' +
            '<div class="leads-dropdown-item" onclick="assignSelected(\\'ava\\')">🤖 Ava</div>' +
            '<div class="leads-dropdown-item disabled">Add SDR...</div>' +
          '</div>' +
        '</div>' +
        '<button class="leads-add-btn" onclick="showAddLeadModal()">+ Add Lead</button>' +
        // Three-dot menu — always on absolute right
        '<div class="leads-dots-wrap" style="position:relative">' +
          '<button class="leads-dots-btn" onclick="toggleLeadsDotsMenu()">⋮</button>' +
          '<div id="leadsDotsMenu" class="leads-dropdown" style="display:none">' +
            '<div class="leads-dropdown-item danger" onclick="bulkDeleteLeads()">🗑 Delete</div>' +
            '<div class="leads-dropdown-item disabled">🔀 Merge</div>' +
          '</div>' +
        '</div>' +
      '</div>' +
    '</div>' +
    '<div id="leadsListContainer">' + renderLeadsTable(leads) + '</div>';
}
```

**CSS for toolbar right-alignment:**
```css
.leads-toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; justify-content: space-between; }
.leads-toolbar-right { display: flex; align-items: center; gap: 8px; }
.leads-count { font-size: 12px; color: #6E6E73; white-space: nowrap; }
```

**Consistent button theming — all primary action buttons must match:**
- All action buttons (Add Lead, Assign, and any primary CTA) should use the same black-on-white scheme: `background: #111; color: #fff; font-weight: 600; border: none; border-radius: 10px;`
- The Assign button is NOT a neutral/border-style button — it matches Add Lead exactly
- **Emoji icon color on dark buttons:** Emojis (👤, etc.) do NOT inherit `color: #fff` from their parent button because they render as system-level color images. Use CSS filter to force them white:
  ```css
  .leads-assign-btn .assign-icon { filter: brightness(0) invert(1); }
  ```
  This converts any emoji to a solid white silhouette. Same technique works for any emoji on dark backgrounds.

**Checkbox column in table:**
```javascript
function renderLeadsTable(leads) {
  return '<table class="leads-table"><thead><tr>' +
    '<th style="width:32px"><input type="checkbox" id="leadsSelectAll" onchange="toggleSelectAllLeads(this.checked)"></th>' +
    '<th>Name</th><th>Account</th><th>Source</th><th>Owner</th><th>Next Activity</th><th>Activity Type</th><th>Created</th>' +
    '</tr></thead><tbody>' +
    leads.map(function(l){
      return '<tr data-id="' + l.id + '" class="lead-row">' +
        '<td><input type="checkbox" class="lead-checkbox" data-id="' + l.id + '" onchange="updateSelectAllCheckbox()"></td>' +
        // ... other cells ...
      '</tr>';
    }).join('') +
    '</tbody></table>';
}
```

**Select-all + individual checkbox logic:**
```javascript
function toggleSelectAllLeads(checked) {
  document.querySelectorAll('.lead-checkbox').forEach(function(cb){ cb.checked = checked; });
}
function updateSelectAllCheckbox() {
  var all = document.querySelectorAll('.lead-checkbox');
  var checked = document.querySelectorAll('.lead-checkbox:checked');
  var sa = document.getElementById('leadsSelectAll');
  if (sa) sa.checked = all.length > 0 && checked.length === all.length;
}
function getSelectedLeadIds() {
  return Array.from(document.querySelectorAll('.lead-checkbox:checked'))
    .map(function(cb){ return cb.getAttribute('data-id'); });
}
```

**Bulk API endpoints:**
```python
@app.post("/api/leads/bulk-assign")
def bulk_assign_leads(data: dict, db: DBSession = Depends(get_db)):
    lead_ids = data.get("lead_ids", [])
    agent = data.get("agent", "ava")
    updated = 0
    for lid in lead_ids:
        l = db.query(Lead).filter(Lead.id == lid).first()
        if l:
            l.assigned_agent = agent
            l.updated_at = utcnow()
            updated += 1
    db.commit()
    return {"ok": True, "updated": updated}

@app.post("/api/leads/bulk-delete")
def bulk_delete_leads(data: dict, db: DBSession = Depends(get_db)):
    lead_ids = data.get("lead_ids", [])
    deleted = 0
    for lid in lead_ids:
        l = db.query(Lead).filter(Lead.id == lid).first()
        if l:
            db.query(ScheduledAction).filter(ScheduledAction.lead_id == l.id).delete()
            db.delete(l)
            deleted += 1
    db.commit()
    return {"ok": True, "deleted": deleted}
```

**Bulk delete confirmation + API call:**
```javascript
async function bulkDeleteLeads() {
  closeLeadsDropdowns();
  var ids = getSelectedLeadIds();
  if (ids.length === 0) { alert('Select leads first'); return; }
  if (!confirm('Delete ' + ids.length + ' lead' + (ids.length > 1 ? 's' : '') + '? This cannot be undone.')) return;
  var r = await fetch('/api/leads/bulk-delete', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ lead_ids: ids })
  });
  if (!r.ok) { alert('Failed to delete leads'); return; }
  renderLeads();
}
```

**Dropdown toggle + outside-click close:**
```javascript
function toggleAssignDropdown() {
  closeLeadsDropdowns();
  var dd = document.getElementById('assignDropdown');
  dd.style.display = dd.style.display === 'block' ? 'none' : 'block';
}
function closeLeadsDropdowns() {
  document.querySelectorAll('.leads-dropdown').forEach(function(d){ d.style.display = 'none'; });
}
document.addEventListener('click', function(e) {
  if (!e.target.closest('.leads-assign-wrap') && !e.target.closest('.leads-dots-wrap')) {
    closeLeadsDropdowns();
  }
});
```

### Batch-fetching Related Data (N+1 Prevention)

When a list endpoint needs to enrich each record with data from a related table, batch-fetch in a single query instead of N+1:

```python
lead_ids = [l.id for l in leads]
next_actions = {}
if lead_ids:
    rows = db.query(ScheduledAction).filter(
        ScheduledAction.lead_id.in_(lead_ids),
        ScheduledAction.status.in_(["pending", "firing"]),
        ScheduledAction.scheduled_at >= now - timedelta(hours=1),
    ).order_by(ScheduledAction.scheduled_at.asc()).all()
    for r in rows:
        if r.lead_id not in next_actions:  # First = earliest
            next_actions[r.lead_id] = {
                "next_activity_at": r.scheduled_at.isoformat(),
                "next_activity_type": r.action_type,
            }

return [{**lead_data, **next_actions.get(l.id, {})} for l in leads]
```

Use a dict with first-wins semantics when you only need the earliest per record.

### Table Column: Owner (Replacing Status with assigned_agent)

When the user requests "Owner" instead of "Status" in the leads table, map directly from `assigned_agent`:

```javascript
var ownerStr = (l.assigned_agent === 'ava' || l.assigned_agent === 'Ava') ? '🤖 Ava'
               : (l.assigned_agent || '—');
```

No DB model change needed — `assigned_agent` already holds owner data. Assign action updates it via PATCH or bulk-assign.

### Search Bar with Debounce

For any list page that needs search, use this pattern:

**Backend** (`server.py`):
```python
@app.get("/api/leads/search")
def search_leads(q: str = "", db: DBSession = Depends(get_db)):
    tenant = db.query(Tenant).first()
    if not tenant: return []
    if not q: return list_leads(tenant.id, db=db)
    q = f"%{q}%"
    leads = db.query(Lead).filter(
        Lead.tenant_id == tenant.id,
        (Lead.name.ilike(q)) | (Lead.phone.ilike(q)) | (Lead.email.ilike(q)) | (Lead.company.ilike(q))
    ).order_by(Lead.created_at.desc()).limit(50).all()
    return serialize(leads)
```

**Frontend** — toolbar with search + add button + count:
```javascript
function renderLeads() {
  cp.innerHTML =
    '<div class="page-title">Leads</div>' +
    '<div class="leads-toolbar">' +
      '<div class="leads-search-wrap">' +
        '<input type="text" placeholder="Search..." id="leadsSearch" oninput="searchLeads()">' +
      '</div>' +
      '<button class="leads-add-btn" onclick="showAddLeadModal()"><span>+</span> Add Lead</button>' +
      '<span class="leads-count">' + leads.length + ' total</span>' +
    '</div>' +
    '<div id="leadsListContainer">' + renderLeadsTable(leads) + '</div>';
}

function searchLeads() {
  var q = document.getElementById('leadsSearch')?.value || '';
  if (window._searchTimer) clearTimeout(window._searchTimer);
  window._searchTimer = setTimeout(function() {
    fetch('/api/leads/search?q=' + encodeURIComponent(q))
      .then(r => r.json())
      .then(leads => { container.innerHTML = renderLeadsTable(leads); });
  }, 250);
}
```

### Lead Creation Modal (Dual Tab: Single Form + CSV Upload)

**Pattern:**
- Two-tab modal: Single Lead (form) + Import CSV (dropzone)
- Tab switching via data-action="switch-lead-tab" + data-tab="single|csv"
- Form fields in a 2-column grid using .form-row
- Required fields (Name, Phone) validated client-side before API call
- Assign to Ava checkbox defaults to checked

**Duplicate detection flow:**
1. On form submit, call GET /api/leads/check-duplicate?phone=...&email=...
2. If duplicates found, show warning with Add Anyway + Cancel buttons
3. If no duplicates, proceed to create
4. Duplicate warning links to existing lead

**Backend duplicate check:**
```python
@app.get("/api/leads/check-duplicate")
def check_duplicate_lead(phone: str = "", email: str = ""):
    # Normalize phone (strip non-digits, compare last 10 digits)
    # Compare email case-insensitively
    return {"duplicates": [{"field": "phone", "value": "...", "existing": "Name", "id": "..."}]}
```

**CSV import flow:**
1. Dropzone with drag-and-drop + file picker (data-action="open-csv-file")
2. File change listener via document.addEventListener('change', ...)
3. Sample CSV download: GET /api/leads/sample-csv
4. Upload as multipart form to POST /api/tenants/{id}/leads/upload-csv
5. Results shown with created/skipped count
6. CSV leads created with assigned_agent=None (unassigned)

**Backend CSV import:**
```python
@app.post("/api/tenants/{tenant_id}/leads/upload-csv")
def upload_leads_csv(tenant_id: str, file: UploadFile = File(...)):
    content = file.file.read().decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        name = (row.get("name") or "").strip()
        if not name: skipped += 1; continue
        lead = Lead(
            tenant_id=tenant_id, name=name, phone=phone or None,
            email=email or None, company=company or None,
            notes=notes or None, lead_source="csv", assigned_agent=None,
        )
        created += 1
    return {"created": created, "skipped": skipped, "errors": errors[:5]}
```

**Sample CSV endpoint:**
```python
@app.get("/api/leads/sample-csv")
def sample_csv():
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(["name", "phone", "email", "company", "notes"])
    return Response(content=output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=leads_sample.csv"})
```

### Created Date + Assignee Display in List Tables

Leads list should show:
- Name (always)
- Account (company + phone below)
- Source
- Status (stage badge + assignee badge below)
- Created (ISO date truncated to YYYY-MM-DD)

```javascript
var assignedStr = l.assigned_agent
  ? (l.assigned_agent === 'ava' ? 'Ava' : l.assigned_agent)
  : '—';
```

### Route Ordering (Critical FastAPI Pitfall)

Static routes MUST be defined BEFORE parameterized routes with the same prefix:

```python
# RIGHT — static before parameterized
@app.get("/api/leads/search")           # Defined first
@app.get("/api/leads/check-duplicate")   # Defined second
@app.get("/api/leads/sample-csv")        # Defined third
@app.get("/api/leads/{lead_id}")         # Parameterized — defined LAST

# WRONG — parameterized before static
@app.get("/api/leads/{lead_id}")         # Defined first — catches everything
@app.get("/api/leads/search")            # Never matched
```

FastAPI/Starlette matches routes in definition order. A parameterized path will capture any single-segment value if defined before static paths with the same shape.

See `references/lead-creation-flow.md` for the full lead creation implementation transcript.

## Domain-Level vs Per-Lead Deals

Greg's design for Hunar.ai's CRM:

- **Deals are org-level**: multiple leads from the same email domain → one deal
- **Domain auto-detection**: extracted from email (with blocklist for gmail.com, yahoo.com, etc.)
- **Fallback**: human manually assigns lead to deal via lead detail page
- **Ava suggests**: Ava can create an `ActionItem` suggesting deal attachment, human confirms
- **Stage progression**: New → Reached Out → Engaged → Qualified → Meeting Booked → Deal Won / Lost / Dormant
- **Trigger**: Deal auto-creates when a lead qualifies or books a meeting. Otherwise manual.

See `references/deal-pipeline-design.md` for the full Q&A transcript and design decisions.

## Action Items (Human Attention Queue)

The `ActionItem` model captures things needing human intervention:
- `suggest_deal`: Ava suggests attaching a lead to a deal
- `escalate`: Lead needs human follow-up
- `review_lead`: Lead data needs review

Surface via:
- **Actions page**: Full list with resolve/dismiss + link to ref entity
- **Sidebar badge**: Red badge on Actions nav item, polls every 15s
- **Ava's chat**: Suggested actions appear in chat panel

## Dashboard Metrics

Dashboard stats grid (computed from `/api/deals/stats`):
| Card | Source |
|------|--------|
| Total Leads | `leads.length` |
| Deals in Pipeline | `stats.total` |
| Meetings Booked | `stats.meetings_booked` |
| Deals Closed | `stats.deal_won` |

No hardcoded ₹0 — deals closed shows real count from deals with stage="closed".

### Inline Searchable Deal Dropdown (Replaces Select)

For lead detail pages where the user attaches a lead to a deal, replace `<select>` with an inline searchable dropdown that shows when clicking "Attach to Deal" or "Change":

```javascript
// In lead detail template string — "Not assigned" state:
'<div style="font-size:12px;color:#9A9A9E;margin-bottom:6px">Not assigned</div>' +
'<button class="lead-btn lead-detail-deal-btn" onclick="toggleDealSearch(event,\'' + l.id + '\')" style="font-size:11px;padding:4px 10px">Attach to Deal</button>'

// The dropdown (hidden by default):
'<div id="dealSearchDropdown-' + l.id + '" class="deal-search-dropdown" style="display:none">' +
  '<input type="text" id="dealSearchInput-' + l.id + '" class="deal-search-input" placeholder="Search deals..." onkeyup="filterDealSearch(event,\'' + l.id + '\')" autocomplete="off">' +
  '<div id="dealSearchResults-' + l.id + '" class="deal-search-results"><div class="deal-search-loading">Loading deals...</div></div>' +
  '<div class="deal-search-create" onclick="showAddDealModalForLead(\'' + l.id + '\')">+ Create Deal</div>' +
'</div>'
```

### Toggle + Fetch + Filter

```javascript
function toggleDealSearch(ev, leadId) {
  if (ev) ev.stopPropagation();
  document.querySelectorAll('.deal-search-dropdown').forEach(function(d){ d.style.display = 'none'; });
  var dd = document.getElementById('dealSearchDropdown-' + leadId);
  if (!dd || dd.style.display === 'block') return;
  dd.style.display = 'block';
  loadDealSearchResults(leadId);
  setTimeout(function(){ document.getElementById('dealSearchInput-' + leadId)?.focus(); }, 50);
}
```

Filtering is client-side — fetch all deals once, then filter by `org_name`, `contact_name`, or `contact_email`:

```javascript
function renderDealSearchResults(leadId, deals, query) {
  var filtered = query
    ? deals.filter(function(d){
        return (d.org_name || '').toLowerCase().indexOf(query) !== -1
          || (d.contact_name || '').toLowerCase().indexOf(query) !== -1
          || (d.contact_email || '').toLowerCase().indexOf(query) !== -1;
      })
    : deals;
  results.innerHTML = filtered.map(function(d){
    return '<div class="deal-search-item" onclick="selectDealFromSearch(\'' + leadId + '\',\'' + d.id + '\')">' +
      '<span class="deal-search-item-name">' + esc(d.org_name) + '</span>' +
      '<span class="deal-search-item-stage">' + esc(d.stage) + '</span></div>';
  }).join('');
}
```

### Select a Deal → Auto-Attach

```javascript
async function selectDealFromSearch(leadId, dealId) {
  await fetch('/api/deals/' + dealId + '/attach-lead', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({lead_id:leadId}) });
  document.getElementById('dealSearchDropdown-' + leadId).style.display = 'none';
  showLeadDetail(leadId);
}
```

### "+ Create Deal" → Modal with Auto-Attach

```javascript
var _dealLeadAttach = null;  // module-level variable

function showAddDealModalForLead(leadId) {
  _dealLeadAttach = leadId;
  showAddDealModal();  // reuses the exact same modal
}
```

Then in `createDealFromModal`, after success:

```javascript
  }).then(function(deal){
    removeAllModals();
    if (_dealLeadAttach) {
      var lid = _dealLeadAttach;
      _dealLeadAttach = null;
      fetch('/api/deals/' + deal.id + '/attach-lead', { method:'POST', ... }).then(function(){
        showLeadDetail(lid);  // stays on lead detail
      });
    } else {
      renderDeals();  // normal flow — goes to deals page
    }
  });
```

### CSS

```css
.deal-search-dropdown { margin-top: 6px; background: #fff; border: 1px solid #E5E5E7; border-radius: 10px; box-shadow: 0 4px 16px rgba(0,0,0,0.08); overflow: hidden; font-size: 12px; }
.deal-search-input { width: 100%; padding: 8px 10px; border: none; border-bottom: 1px solid #E5E5E7; font-size: 12px; font-family: inherit; outline: none; box-sizing: border-box; background: #FAFAFA; }
.deal-search-input:focus { background: #fff; }
.deal-search-results { max-height: 180px; overflow-y: auto; }
.deal-search-item { padding: 8px 10px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; transition: background 0.1s; }
.deal-search-item:hover { background: #F5F5F7; }
.deal-search-item-name { font-weight: 600; color: #111; }
.deal-search-item-stage { font-size: 10px; color: #6E6E73; text-transform: uppercase; letter-spacing: 0.3px; }
.deal-search-create { padding: 10px; text-align: center; color: #2563eb; font-weight: 600; cursor: pointer; border-top: 1px solid #E5E5E7; }
.deal-search-create:hover { background: #F0F5FF; }
```

### Outside-Click Close

Append to the existing `document.addEventListener('click', ...)` handler:

```javascript
var anyDealDropdown = document.querySelector('.deal-search-dropdown[style*="display: block"]');
if (anyDealDropdown && !e.target.closest('.deal-search-dropdown') && !e.target.closest('.lead-detail-deal-btn')) {
  anyDealDropdown.style.display = 'none';
}
```

The `.lead-detail-deal-btn` class on the toggle button prevents closing when the user clicks the button to re-open. The `stopPropagation()` in `toggleDealSearch` prevents the document handler from closing it immediately after opening.

### Key Design Decisions

- **Inline onclick** is used here (violating the event-delegation preference) because the lead ID is embedded in the template string and the functions are simple toggles/fetches. This is a legitimate exception — per-instance inline handlers for dynamic content rendered via template strings.
- **Client-side filtering** — fetches all deals once, filters in the browser. Acceptable for <500 deals. For larger pipelines, add server-side search.
- **The same "+ Create Deal" modal** is reused from the Deals page — no duplicate UI. The `_dealLeadAttach` variable adds lead-context behavior without changing the modal itself.

## Select-then-Assign Modal Pattern (Lead Attachment)

When building modals where the user selects from a list then confirms, use this two-step pattern instead of inline action buttons:

```javascript
function showAttachDealModal(leadId) {
  // ... fetch deals, generate options HTML ...
  var modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.innerHTML = '<div data-action="stop-propagation">' +
    '<h3>Attach to Deal</h3>' +
    '<p>Select a deal:</p>' +
    '<div class="deal-option-list">' + optionCards + '</div>' +
    '<button class="form-btn primary" id="assignBtn" disabled>Assign</button>' +
    '<button class="form-btn secondary" data-action="close-modal">Cancel</button>' +
    '</div>';
  document.body.appendChild(modal);

  // Step 1: Click a deal option → highlight it, enable Assign
  modal.querySelectorAll('.deal-option').forEach(function(el) {
    el.addEventListener('click', function() {
      modal.querySelectorAll('.deal-option').forEach(o => o.classList.remove('selected'));
      this.classList.add('selected');
      document.getElementById('assignBtn').disabled = false;
    });
  });

  // Step 2: Click Assign → confirm action
  modal.querySelector('#assignBtn').addEventListener('click', function() {
    attachLeadToDeal(leadId, selectedDealId);
  });

  // Step 3: Close-modal on overlay click + cancel
  modal.addEventListener('click', function(e) {
    var a = e.target.getAttribute && e.target.getAttribute('data-action');
    if (a === 'close-modal') { modal.remove(); }
    else if (a === 'stop-propagation') { e.stopPropagation(); }
  });
}
```

**Key design decisions:**
- Uses `document.createElement` + `appendChild` (not `insertAdjacentHTML`) — needed for adding event listeners to inner elements after DOM insertion
- Every deal option gets a direct `click` listener (not delegated) to avoid stale references
- Assign button starts `disabled` — enables only when a deal is selected
- Cancel uses `data-action="close-modal"` with the overlay's own click handler — must NOT rely on event delegation from a parent container (the modal is appended to `document.body`, outside `#centerPanel`)
- Deal options styled as `.deal-option` cards with name + stage side-by-side, `.selected` class adds dark border + box-shadow
- `.deal-option-list` has `max-height: 240px` with `overflow-y: auto` for many deals

**Pitfall — modal outside centerPanel:** When a modal is appended to `document.body` (not inside `#centerPanel`), the global event delegation handler on `#centerPanel` will NOT catch clicks inside it. The modal MUST attach its own event listeners. This is why `showAttachDealModal()` uses `modal.addEventListener('click', ...)` directly — the alternative is to append the modal inside `#centerPanel`, which risks conflicts with the panel's rendering logic.

## Lead Detail 4-Column Card Pattern

The lead detail view uses a CSS grid for the info columns (Lead Info, Company, Contact, Deal) with Notes full-width below:

```css
.lead-card-inner { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; }
.lead-card-section { padding: 20px 16px 24px; border-right: 1px solid #E5E5E7; min-width: 0; word-break: break-word; }
.lead-card-section:nth-child(4) { border-right: none; }
.lead-card-section.lead-notes { grid-column: 1 / -1; border-top: 1px solid #E5E5E7; padding-top: 16px; margin-top: 0; }
```

**Critical:** `min-width: 0` on grid items is **required** — without it, content (especially long text or `min-width` on child elements like flex labels) forces grid tracks wider than their `1fr` share, making columns uneven.

**Notes section:** Spans all 4 columns via `grid-column: 1 / -1`. The last column (Deal) removes its right border via `:nth-child(4)`, not `:last-child`, since Notes is the actual last child.

### Lead Notes Pattern

Notes on leads are stored as timestamped entries in the `Lead.notes` Text column. See `references/lead-notes-pattern.md` for full implementation:

- **Storage format:** Each line is `[timestamp] Type: content` (Stage change, Note, or System)
- **Backend:** Both `PATCH /api/leads/{id}` and `update_lead` tool APPEND notes with a timestamp — never overwrite. Except when `notes_action: "replace"` is passed in the request body, which causes a full overwrite (used by the edit mode form).
- **Frontend:** Structured rendering with colored icons, type badges, and timestamp in timeline-style entries
- **Quick-add:** "+ Add Note" button in the Notes tab opens an inline form → appends via PATCH
- **Edit mode:** Notes textarea fetches live data from API and appears at bottom of lead card. Saves with `notes_action: 'replace'` for full overwrite.
- **Agent tool:** Ava calls `update_lead` with `fields: {notes: "..."}` to record context from WhatsApp conversations

See `references/lead-notes-pattern.md` for full implementation (both append and replace modes).  
See `references/api-datetime-ist-formatting.md` for the IST timezone API datetime pattern.

Any time the frontend JS builds HTML via string concatenation with user/lead data, an `esc()` helper is required to prevent XSS and broken rendering:

```javascript
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
```

**Where needed:** Template literals that interpolate user-provided data (lead names, company names, notes, tooltip text). If the function doesn't exist, the catch block in `showLeadDetail()` will fire silently and the lead detail page won't render.

**Pitfall:** `esc()` is **not** defined globally or imported — each ARA template file that uses it must define its own copy at the top of the JS block. Forgetting it causes a silent crash (caught by the `try/catch` in `showLeadDetail`).

## Cadence Builder — Pattern B Config Screen Architecture (v3)

The Cadence Builder at `/cadence` has evolved through three versions. v3 is the current canonical reference for Pattern B (config screen without Ava chat).

### Page Layout (top-to-bottom)

```
┌── LEAD → CADENCE MAPPING strip (compact, no changes) ──┐
├── ❄️ 🔥 🌱 Template cards (3 selectable cards) ───────┤
│     Each card: icon + title + desc + active indicator    │
│     Click switches template — unsaved changes prompt     │
├── 🎨 Brand Voice bar (per-template) ────────────────────┤
│     Tone chips (Formal/Warm/Casual/Funny)               │
│     No-nos tags (add/remove via ✕)                      │
│     Formality slider (1=Casual → 5=Formal)               │
├──────────────────── 50/50 SPLIT ────────────────────────┤
│ LEFT COLUMN                        RIGHT COLUMN          │
│ 🎯 Primary Goal (text input)       ✨ Preview (LLM-gen)  │
│ 💬 Step card (clickable)           🟢 Reachout Cond.     │
│   · Channel icon + name            🔴 Stop Conditions    │
│   · Delay: "Day 4 · +96h ✏️"       (side-by-side cards)  │
│   · Structured fields per channel                         │
│     (WhatsApp=3, Email=4, Call=4, SMS=2)                 │
│   · ✕ delete button                                       │
│ ✉️ Step card                                             │
│ 📞 Step card                                             │
│ [+ Add Step] (opens channel picker modal)                 │
├──────────────────────────────────────────────────────────┤
│                   [Reset] [Publish Cadence]               │
└──────────────────────────────────────────────────────────┘
```

### Structured Step Fields (Per-Channel)

Each channel type gets its own set of objective fields — the user writes exactly what goes where, and the LLM fills in good language around the structure. This replaces the single `desc` textbox approach that required LLM iteration.

```javascript
// STEP_FIELDS — per-channel field sets
var STEP_FIELDS = {
  whatsapp: [
    {key:'opening', label:'Opening', placeholder:'Hook / personalization'},
    {key:'value', label:'Value', placeholder:'Core value proposition'},
    {key:'cta', label:'CTA', placeholder:'Call to action'}
  ],
  email: [
    {key:'subject', label:'Subject', placeholder:'Email subject line'},
    {key:'opening', label:'Opening', placeholder:'First paragraph'},
    {key:'body', label:'Body', placeholder:'Value prop / details'},
    {key:'cta', label:'CTA', placeholder:'Call to action'}
  ],
  call: [
    {key:'greeting', label:'Greeting', placeholder:'Context / opener'},
    {key:'value', label:'Value', placeholder:'Why call now'},
    {key:'question', label:'Question', placeholder:'Key discovery question'},
    {key:'cta', label:'CTA', placeholder:'Closing ask'}
  ],
  sms: [
    {key:'hook', label:'Hook', placeholder:'One-line value'},
    {key:'cta', label:'CTA', placeholder:'Next step'}
  ]
};
function defaultFields(channel) { /* generates empty fields object */ }
```

**Step data structure (in localStorage):**
```javascript
{channel:'whatsapp', day:0, delay:0, fields:{opening:'...', value:'...', cta:'...'}}
```

**Migration from old `desc` format:** Detect `!s.fields`, create empty fields via `defaultFields(s.channel)`, put old `desc` into the first field key. Run on every `loadData()`.

**Rendering:** Iterate `STEP_FIELDS[channel]`, render each as `.sf-row` with `.sf-label` + `.sf-input`. Inputs have `data-step` and `data-field` attributes for DOM→state reading.

**Saving:** In `saveCurrentState()`, query all `.sf-input`s inside each step card. Read `data-step` and `data-field` attributes, write values into `t.steps[i].fields[key]`. NEVER clear `t.steps` before re-saving (see pitfall below).

**CSS:** Compact layout — 9px labels, 10px inputs, 4px gap, 3px margin-bottom. Inputs start with `background:#FAFAFC` and turn `#fff` on focus.

### Preview — Manual Regeneration Only (User Preference)

**Preview does NOT auto-regenerate on any click, selection, or change.** It ONLY generates when the 🤖 ⟳ Regenerate button is clicked. This is Greg's explicit preference — confirmed after auto-regeneration on tone/formality/field changes was frustrating.

Pattern:
- `selectStep()` → calls `resetPreview()` — shows empty state "🤖 Click ⟳ Regenerate to preview"
- Tone/formality/field changes → sync to memory only, no preview call
- Regenerate button → reads current memory state → calls `POST /api/cadence/preview`
- Header always shows which step is selected (channel + number), body stays empty until regen

```javascript
function resetPreview() {
  document.getElementById('previewBody').innerHTML = '🤖 Click <strong>⟳ Regenerate</strong> to preview<br>Ava\'s generated communication';
}
```

### LLM Preview Endpoint (structured fields)

`POST /api/cadence/preview` builds a system prompt with:
1. Channel-specific guidelines (WhatsApp=punchy 2-3 lines, Email=subject+3-4 paragraphs, Call=talking points)
2. Tone and formality from brand voice
3. No-nos as "NEVER use" constraints
4. Field-by-field user instructions — each field becomes a line like `  Subject line: Quick thought on...`
5. Lead context (name, company, city, industry)

The prompt instructs the LLM to respond with ONLY the message text — no explanations, quotes, or markdown. Falls back to `generate_fallback_preview()` with hardcoded static text if the LLM call fails.

### Per-Template State Management

Each template (Cold/Inbound/Nurture) has its own brand voice, primary goal, steps, and conditions. All persisted to a single `localStorage` key (`ara_cadence_data`).

**Unsaved changes detection:** Track `hasUnsavedChanges` flag. On template switch, compare `goalInput.value` against saved objective. If changed, show confirm dialog overlay before switching.

**Confirm dialog pattern:** Fixed overlay (`position:fixed; z-index:300`) with title, message, Cancel and Switch buttons. On confirm: save current state + switch to target. On cancel: dismiss, keep current template.

### Timing Normalization — Monotonic Non-Decreasing Constraint

Step timings must satisfy: **each step's cumulative time ≥ the previous step's cumulative time**. This prevents a later step from firing before an earlier one.

**The constraint:** `cumulative(i) = steps[i].day * 24 + steps[i].delay`. For all i >= 1: `cumulative(i) >= cumulative(i-1)`. Step 0 is always Day 0·+0h.

**`normalizeTimings()` function** — enforces the constraint after every timing-affecting operation:

```javascript
function normalizeTimings() {
  var t = getTemplate();
  if (!t || !t.steps || t.steps.length < 2) return;
  var steps = t.steps;
  steps[0].day = 0; steps[0].delay = 0;  // Hard lock step 1
  for (var i = 1; i < steps.length; i++) {
    var prevCum = steps[i-1].day * 24 + steps[i-1].delay;
    var currCum = steps[i].day * 24 + steps[i].delay;
    if (currCum < prevCum) {
      steps[i].day = steps[i-1].day;       // Bump to match predecessor
      steps[i].delay = steps[i-1].delay;
    }
  }
}
```

**Triggered on three entry points:**
1. `doneDelay(index)` — after the user edits a step's delay and clicks ✓
2. `addStep(channel)` — after pushing a new step at 0/0
3. Drag-drop `drop` handler — after splice into new position (replaces old force-recalculate approach)

**Behavior by example:**
- Edit Step 2 to **3d 0h** (cumulative 72h) → Steps 3, 4 auto-bump from 0d 0h to **3d 0h**
- Edit Step 3 to **1d 6h** (30h, already after Step 2's 0h) → kept as-is, no change
- All steps at 0d 0h → no-op (trivially satisfied)
- Reorder Step 4 before Step 2 → the moved step keeps its timing, normalization bumps any backward steps forward

This logic replaces the old approach of force-recalculating all timestamps to `day=i, delay=24` after every reorder. Users now set their own delays; the system only enforces the constraint boundary.

### Pitfalls — Cadence Builder

- **`saveCurrentState()` must NEVER clear `t.steps`:** The bug was `t.steps = []` followed by a non-functional forEach loop, then `var existing = t.steps || []` (always empty). Fix: remove the `= []` line and update descriptions in-place using DOM `sf-input` values. Steps array preserves channel, day, delay while DOM provides field descriptions.
- **localStorage data corruption recovery:** If a prior bug saved empty step arrays, `loadData()` must detect and repair: `if (!data[key].steps || data[key].steps.length === 0) data[key].steps = JSON.parse(JSON.stringify(DEFAULT_TEMPLATES[key].steps))`. Always validate saved data before trusting it.
- **`esc()` must be defined per-file:** Every ARA template file that builds HTML with user data needs its own `esc()` function. It's not shared or globally available. Missing `esc()` causes a silent catch-block crash in `showLeadDetail()`.
- **Never use inline `onchange` with string args in Python templates:** The quoting hell is documented above. Always use `data-*` attributes + event delegation.
- **Add Step must initialize fields:** When creating a new step, call `defaultFields(channel)` to populate empty fields. Old code that set `desc:''` without fields will break structured rendering.
- **Old `desc` → fields migration runs every load:** After fixing the `t.steps = []` bug, old localStorage data may still have empty step arrays. The migration check (`!s.fields`) runs per-step on every `loadData()` and works even after the array-size fix.
- **Brand voice memory sync before preview:** When a visual UI control (tone chip, formality slider) changes brand voice state, the handler MUST write the new value to `getTemplate().brandVoice` in memory. The visual DOM is NOT the source of truth. If you update a CSS class or label text without syncing to the in-memory model, any later function that reads `t.brandVoice` (preview generation, save, API call) will get stale data. This applies to ANY visual-only state change that feeds into a downstream operation.
- **Event delegation + input click trap:** When step cards have `data-action` on the outer div and inputs inside them, `e.target.closest('[data-action]')` finds the card even on input clicks. This triggers step selection + full re-render, stealing focus from the input. Fix: check `e.target.tagName === 'INPUT' || 'TEXTAREA' || 'BUTTON'` before dispatching the action. Applies to any delegated handler where clickable cards contain interactive form elements.
- **Drag-drop timing normalization:** After any step reorder, call `normalizeTimings()` to enforce the monotonic constraint. Do NOT force-recalculate all timings to `i/+24h` — the user sets their own delays, and the normalization only bumps forward steps that precede their predecessor. Each step's cumulative time (`day*24 + delay`) must be >= the previous step's. The normalization function also hard-locks step[0] to Day 0·+0h. Called after: `doneDelay()`, `addStep()`, and the drop handler. **Visual hint:** Set step card borders to `1px dashed #D0D0D5` (instead of solid) to signal draggability. The `.dragging` and `.drag-over` states already use `dashed` — the base state should match so the visual language is consistent. See `references/drag-drop-reorder-steps.md` for the canonical implementation.
- **Delay editor hours normalization (0-23 with overflow):** The hours input must have `max="23"` and the `doneDelay()` save handler must normalize: `days += Math.floor(hours / 24); hours = hours % 24;`. This means 25h becomes Day+1, 1h — no manual correction needed. Display the current value as `delay % 24` so existing data with 48h appears as 0h with the day already correct.
- **Step 1 delay hard-locked at Day 0·+0h:** The first step of any cadence must always be Day 0·+0h. This is enforced in three places: (1) DEFAULT_TEMPLATES ship with it, (2) `doneDelay()` checks `if (index === 0) { days = 0; hours = 0; }`, (3) `normalizeTimings()` always resets step[0] as the first operation. Users cannot edit this — attempts to change it snap back on save or after the next normalization cycle.

## ℹ️ Tooltip Pattern (Hover Info)

For inline info tooltips without a JS library:

```html
<span class="cad-info">i<span class="cad-tooltip">Tooltip text here</span></span>
```

```css
.cad-info {
  display: inline-flex; align-items: center; justify-content: center;
  width: 14px; height: 14px; border-radius: 50%;
  background: #E5E5E7; color: #6E6E73;
  font-size: 9px; font-weight: 700; cursor: help;
  position: relative; vertical-align: super; margin-left: 3px;
}
.cad-tooltip {
  display: none; position: absolute; bottom: calc(100% + 6px);
  left: 50%; transform: translateX(-50%);
  background: #333; color: #fff; font-size: 10px; font-weight: 400;
  padding: 4px 8px; border-radius: 6px; white-space: nowrap;
  z-index: 10; pointer-events: none;
}
  .cad-info:hover .cad-tooltip { display: block; }
  
  **Cadence select width pitfall:** When a `<select>` (or any inline form element) is rendered inside a `1fr` grid column with `min-width: 0`, the select's intrinsic width is based on the longest `<option>` text. If the column is narrow enough, text wraps vertically, rendering option text unreadable. Fix: set the select to `width: 100%; min-width: 0` and the parent flex row to `flex-wrap: wrap`. The `width: 100%` forces the select to fill its available column width, and `flex-wrap` lets the label sit above if the space is too tight for row layout.
```

The `i` character renders as a small circled info icon. `vertical-align: super` positions it as a superscript. The tooltip appears above on hover.

## Cadence Auto-Assignment Pattern

When leads need automatic cadence assignment with manual override tracking:

### DB Fields (on Lead model)
```python
cadence_type = Column(String, default="cold")        # cold, inbound, nurture
cadence_auto_assigned = Column(String, default="yes") # "yes" or "no" 
cadence_updated_at = Column(DateTime, nullable=True)
```

### Backend Logic (`server.py`)
```python
CADENCE_MAPPING = [
    (lambda s, st: s in ('form', 'meta', 'google', 'referral') and st != 'dormant', 'inbound', 'Inbound (Hot Lead)'),
    (lambda s, st: st in ('dormant', 'lost'), 'nurture', 'Nurture / ABM'),
]
def determine_cadence(source, stage):
    for match_fn, ctype, _ in CADENCE_MAPPING:
        if match_fn(source, stage): return ctype
    return 'cold'
```

On lead creation: call `determine_cadence()` and set `cadence_auto_assigned='yes'`.
On manual update (PATCH): when `cadence_type` is in the update payload, set `cadence_auto_assigned='no'` to track the override.

### API — PATCH cadence endpoint
```python
@app.patch("/api/leads/{lead_id}/cadence")
def update_lead_cadence(lead_id: str, data: dict, db: DBSession = Depends(get_db)):
    l = db.query(Lead).filter(Lead.id == lead_id).first()
    if not l: raise HTTPException(404)
    l.cadence_type = data.get("cadence_type", l.cadence_type)
    l.cadence_auto_assigned = "no"
    l.cadence_updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "ok"}
```

### UI — Cadence selector with ℹ️ tooltip (in Deal column)
```javascript
function cadenceHTML(l) {
  var ct = l.cadence_type || 'cold';
  var auto = l.cadence_auto_assigned;
  var dateStr = l.cadence_updated_at ? new Date(l.cadence_updated_at).toLocaleDateString(...) : '';
  var tipText = auto === 'yes' ? 'Auto-assigned' + (dateStr ? ' ' + dateStr : '')
                : (dateStr ? 'Manually set ' + dateStr : 'Manually set');
  return '<div class="cadence-row"><span>Cadence:</span>' +
    '<select data-action="change-cadence" data-lead-id="' + l.id + '" data-cadence-val="' + ct + '">' +
    '<option value="cold"' + (ct==='cold'?' selected':'') + '>Cold Outreach</option>' +
    '<option value="inbound"' + (ct==='inbound'?' selected':'') + '>Inbound (Hot Lead)</option>' +
    '<option value="nurture"' + (ct==='nurture'?' selected':'') + '>Nurture / ABM</option>' +
    '</select>' +
    '<span class="cad-info">i<span class="cad-tooltip">' + esc(tipText) + '</span></span></div>';
}
```

The `change` event listener uses `e.target.closest('[data-action="change-cadence"]')` to catch dropdown changes — NEVER use inline `onchange` with quote-escaping in Python template strings (see quoting trap pitfalls below).

## Pitfalls

- **Route ordering**: `GET /api/deals/stats` MUST be defined BEFORE `GET /api/deals/{deal_id}` or FastAPI interprets "stats" as a deal_id
- **Python-JS escaping**: Triple-quoted Python strings (`"""..."""`) are brutal for JS. The core issue: Python consumes `\'` as an escaped quote → just `'` in output. To get `\'` in output, the file needs `\\'` (two backslashes + quote in Python source).

**⚠️ Patch-tool backslash doubling:** The `patch` tool interprets `\\` differently inside Python raw strings. When you patch a line like `Hunar\\'s` (a backslash-escaped apostrophe in the JS), the patch tool may write `Hunar\\\\'s` — doubling the backslashes. This turns valid JS `Hunar\\'s` → `Hunar\\\\'s` in the file, which JS reads as escaped backslash (`\\\\`) followed by string-terminating `'`. Always validate with `node --check` on extracted JS after any patch to Python raw strings containing JS. Use byte-level inspection (see verification workflow below) if the error location seems wrong.

**⚠️ `\n` absorbed by Python triple-quoted strings:** Inside `"""..."""`, Python interprets `\n` as an actual newline character (U+000A), NOT the literal string `\n`. This means JS escape sequences like `$1\n'` (intended as dollar-1-backslash-n-quote in JS) become `$1<newline>'` — breaking the JS string literal. To output a literal `\n` JS escape sequence, the Python source must use `\\n` (two backslashes + n), which Python renders as backslash + n in the output.

  ```python
  # WRONG — Python renders \n as actual newline
  '... tier.label.replace(/(.{4})/, \'$1\n\') ...'
  # After Python processing: ...$1
  #                        ')...          ← BROKEN JS

  # RIGHT — Python preserves \\n as literal backslash-n
  '... tier.label.replace(/(.{4})/, \'$1\\n\') ...'
  # After Python processing: ...'$1\n')...   ← Valid JS
  ```

  The same applies to any JS escape sequence: `\t`, `\r`, `\u00a0`, etc. Always double the backslash in the Python source to produce a literal backslash in the JS output.

Three fix approaches, in preference order:

  **Fix #1 — Event delegation (PREFERRED):** Never use inline onclick with string arguments. Use `data-*` attributes and a single delegated listener. The existing codebase already uses this pattern for lead rows:
  ```python
  # Python template builds HTML with data attributes (no quotes to escape)
  '<div class="deal-card" data-id="' + d.id + '">'
  ```
  ```javascript
  // JS event delegation — single listener at bottom of script
  document.getElementById('centerPanel').addEventListener('click', function(e) {
      var card = e.target.closest('.deal-card');
      if (card) showDealDetail(card.dataset.id);
  });
  ```

  **Fix #2 — `&apos;` HTML entity:** For inline onclick handlers in innerHTML strings, use `&apos;` instead of `'` for string arguments. `&apos;` survives all layers (Python → JS string → innerHTML → HTML attribute → onclick) with ZERO backslash escaping:
  ```python
  # No backslashes needed — &apos; is just text
  '<button onclick="showDealDetail(&apos;' + d.id + '&apos;)">View</button>'
  ```
  Browser parses `&apos;` → `'` in the onclick attribute → valid JS string argument.

  **Fix #3 — Pass raw variable:** For onmouseover/onmouseout color changes, pass the color value as a data attribute and reference it, or use CSS `:hover` instead of JS:
  ```python
  # Instead of inline onmouseover with escaped color code:
  # onmouseover="this.style.borderColor=\'#D0D0D5\'"
  # Use CSS class:
  '<div class="deal-card deal-card-hoverable" ...>'
  ```
  ```css
  .deal-card-hoverable { border-color: #E5E5E7; transition: border-color 0.1s; }
  .deal-card-hoverable:hover { border-color: #D0D0D5; }
  ```

  **Verification workflow for escaping issues:**
  1. `curl http://localhost:8766/dashboard > /tmp/page.html` — grab the rendered page
  2. Extract script: `python3 -c "import re; open('/tmp/j.js','w').write(re.search(r'<script>(.*?)</script>', open('/tmp/page.html').read(), re.DOTALL).group(1))"`
  3. `node --check /tmp/j.js` — must exit 0 with no errors
  4. If error: check the exact bytes at the reported position with `python3 -c "print(repr(open('/tmp/j.js').read().split('\\n')[N-1]))"` and look at individual chars with a byte scan
  5. When `node --check` reports a cryptic error like "Unexpected identifier 's'" or "Unexpected identifier 've'" — this usually means a `\\` instead of `\` before an apostrophe. The `'` that should be part of the string (escaped by `\`) is instead terminating the string, and the next character ('s', 've', etc.) becomes an unexpected identifier. Fix: check the file at the byte level — read the source Python file in `'rb'` mode and count actual backslash bytes before the suspect quote.
  6. In browser: `browser_navigate` → `browser_console` → verify `typeof showPage === 'function'`

  See `references/js-escaping-debug-workflow.md` for the full debugging workflow including byte-level inspection, `node --check` error decoding, and automated binary fix patterns.

- **SQLite ALTER TABLE**: `Base.metadata.create_all()` won't add columns to existing tables. Use raw SQL for schema migrations.

- **SQLAlchemy NULL comparison trap**: `col != "value"` silently excludes rows where `col IS NULL` (SQL treats `NULL != 'value'` as UNKNOWN, not TRUE). This is the #1 recurring bug in ARA queries. When filtering out a specific value, always use `or_(col != "value", col.is_(None))`:
  ```python
  from sqlalchemy import or_
  # Before applying this fix, always import or_:
  # from sqlalchemy import and_, or_
  
  # WRONG — excludes NULL rows
  query.filter(ActionItem.outcome_state != "resolved")
  
  # RIGHT — includes both non-resolved and NULL
  query.filter(or_(ActionItem.outcome_state != "resolved", ActionItem.outcome_state.is_(None)))
  ```
  The `is_(None)` is the SQLAlchemy equivalent of `IS NULL`. Using `== None` doesn't work for SQL NULL semantics.

- **innerHTML &lt;script&gt; tags don't execute**: Browsers refuse to run `<script>` tags injected via `innerHTML` — this is a W3C security spec, not a bug. Any `<script>loadActionsForLead('...')</script>` inside an innerHTML string is dead code. Fix: call the function directly after the innerHTML assignment:
  ```javascript
  cp.innerHTML = '...';       // Render HTML
  loadActionsForLead(l.id);   // Execute immediately after
  ```

- **innerHTML onclick escaping → data-attributes**: Using `\'` to escape quotes inside onclick attributes fails because the HTML parser un-escapes before JS execution. The `\'` that was intended as JS string delimiter becomes a raw `'` that closes the HTML attribute. Fix: never inline onclick with string args. Use `data-*` attributes + `this.dataset`:
  ```javascript
  // WRONG — broken by HTML/JS escaping layers
  '<button onclick=\"func(\'' + id + '\')\">Click</button>'
  
  // RIGHT — data attributes survive all layers
  '<button data-id=\"' + id + '\" onclick=\"func(this.dataset.id)\">Click</button>'
  ```

- **SCP overwrite pitfall**: When fixing a file directly on the production server (via SSH + Python script), then SCP-ing the local copy next time you deploy, the local copy overwrites the server-fixed version. Pattern: either (a) run all fix scripts AFTER every SCP deploy, or (b) maintain the fix scripts as a server-side maintenance tool, or (c) sync back from server before making local changes. The `fix_tests.py` pattern (run on server after deploy) is the current convention.
- **Deal create triggers**: Don't auto-create deals for `new` stage leads — only for `qualified` or higher. Cold leads don't warrant a deal.
- **Activity pagination**: `/api/activities` defaults to 50 items. For high-volume pipelines, add limit/offset pagination early.
- **Action badge polling**: 15s interval. Don't poll faster — it wastes API credits and DB connections.
- **Checkbox inside clickable row event trap:** When table rows are clickable (`.lead-row` navigates to detail via event delegation) and contain checkboxes, clicking a checkbox bubbles up to the row handler and navigates away. Fix in two places:
  1. In the event delegation handler, check the target before navigating:
     ```javascript
     var leadRow = t.closest('.lead-row');
     if (leadRow) {
       if (t.tagName === 'INPUT' && t.type === 'checkbox') return;  // <-- skip navigation
       showLeadDetail(leadRow.dataset.id);
     }
     ```
  2. Also skip for toolbar buttons/dropdowns inside the row area:
     ```javascript
     if (t.closest('.leads-dropdown')) return;
     if (t.closest('.leads-assign-btn') || t.closest('.leads-dots-btn') || t.closest('.leads-add-btn')) return;
     ```
  This applies to ANY delegated handler where clickable containers hold interactive elements.

See `references/leads-table-bulk-actions.md` for the full session implementation including the event delegation fix and all CSS classes.
