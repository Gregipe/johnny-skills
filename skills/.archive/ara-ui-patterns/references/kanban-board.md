# Deals Pipeline Kanban Board (Compact Chip Design)

Rendered by `renderDeals()` in `/Users/greg/ara/static/dashboard.js`. CSS in `dashboard_template.py`.

## Design Goals

- **All 8 stages fit on one screen** — no horizontal scrolling at 1280px viewport
- **Chips instead of cards** — each deal is a small pill showing just the name and value
- **Click-to-reveal** — clicking a chip opens a right-side slide-in detail panel
- **Vertically stacked chips** — deals stack top-to-bottom in each column, never side-by-side
- **Dynamic column widths** — columns grow/shrink based on their content
- **Uniform headers** — stage name and count badge on one line, border line at same level for all columns

## Layout

```
1280px viewport
├── Sidebar (240px fixed)
├── Center Panel (flex:1, padding 24px)
│   ├── Page title + subtitle
│   └── Kanban row (display:flex; gap:8px)
│       ├── NEW column (flex:1 1 auto) ─── header + chips (stacked) + [+]
│       ├── REACHED OUT (flex:1 1 auto)
│       ├── ENGAGED (flex:1 1 auto)
│       ├── QUALIFIED (flex:1 1 auto)
│       ├── MEETING BOOKED (flex:1 1 auto)
│       ├── WON (flex:1 1 auto)
│       ├── LOST (flex:1 1 auto)
│       └── DORMANT (flex:1 1 auto)
└── Chat Panel (380px fixed)
```

**Key:** Each column uses `flex:1 1 auto` — columns start from their content width and grow proportionally. Longer names like "Meeting Booked" get more space; short names like "Won" get less. `overflow:hidden` on the column prevents content from leaking.

## Column Structure

```html
<div class="deal-stage-col" style="flex:1 1 auto; min-width:0; overflow:hidden; border-radius:10px; padding:8px; display:flex; flex-direction:column">
  <!-- Header -->
  <div class="deal-stage-header">
    <span class="stage-label">STAGE NAME</span>
    <span class="count">N</span>
  </div>

  <!-- Chips (stacked vertically) -->
  <div class="deal-chip-row">
    <span class="deal-chip" data-deal-id="...">Deal Name</span>
    <span class="deal-chip" data-deal-id="...">Other Deal</span>
  </div>

  <!-- Empty state (when no deals) -->
  <div>—</div>

  <!-- Add button -->
  <button class="deal-add-tiny">+</button>
</div>
```

## CSS

### Column
```css
.deal-stage-col { flex: 1 1 auto; min-width: 0; overflow: hidden; background: #FAFAFA; border: 1px solid #E5E5E7; border-radius: 10px; padding: 8px; display: flex; flex-direction: column; }
```

### Header (uniform level, truncates long names)
```css
.deal-stage-header { font-size: 9px; font-weight: 600; color: #111; text-transform: uppercase; letter-spacing: 0.3px; padding-bottom: 6px; margin-bottom: 6px; border-bottom: 1.5px solid #E5E5E7; display: flex; justify-content: space-between; align-items: center; white-space: nowrap; gap: 4px; }
.deal-stage-header .count { color: #111; font-size: 10px; background: #F0F0F2; padding: 1px 6px; border-radius: 6px; flex-shrink: 0; }
.deal-stage-header .stage-label { overflow: hidden; text-overflow: ellipsis; min-width: 0; }
```

`white-space: nowrap` prevents multi-word names from wrapping. The `.stage-label` span handles truncation with ellipsis when the column is too narrow for the full name. `.count` has `flex-shrink: 0` so the badge never gets squeezed.

### Chips (stacked vertically)
```css
.deal-chip-row { display: flex; flex-direction: column; gap: 3px; padding: 2px 0; }
.deal-chip { display: flex; align-items: center; gap: 4px; padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 500; color: #111; background: #fff; border: 1px solid #E5E5E7; cursor: pointer; transition: all 0.12s; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; width: 100%; box-sizing: border-box; }
.deal-chip:hover { border-color: #2563eb; background: #EEF2FF; color: #2563eb; transform: translateY(-1px); box-shadow: 0 2px 6px rgba(37,99,235,0.12); }
.deal-chip .chip-val { font-size: 9px; color: #111; font-weight: 600; }
```

**Important:** Chips use `flex-direction: column` (not `flex-wrap: wrap`) so deals always stack top-to-bottom, one per row. Each chip is `width: 100%` to fill the column. Column div MUST have `overflow: hidden` — the count badge is `flex-shrink: 0` so it never gets clipped, but the stage label truncates with ellipsis when the column is narrow.

### Tiny Add Button
```css
.deal-add-tiny { display: flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 5px; border: 1px dashed #D0D0D5; background: transparent; color: #111; font-size: 12px; cursor: pointer; transition: all 0.12s; flex-shrink: 0; margin-top: 4px; }
.deal-add-tiny:hover { border-color: #2563eb; color: #2563eb; background: #EEF2FF; }
```

## Event Delegation (no inline onclick)

Chips and add buttons use a single click listener on `#centerPanel` via `data-*` attributes:

```javascript
cp.addEventListener('click', function(e) {
  var chip = e.target.closest('.deal-chip');
  if (chip && chip.dataset.dealId) { showDealModal(chip.dataset.dealId); return; }
  var addBtn = e.target.closest('.deal-add-tiny');
  if (addBtn && addBtn.dataset.stage) { showAddDealModal(addBtn.dataset.stage); return; }
});
```

## Slide-in Detail Panel

Clicking a chip opens a right-side slide panel:

```javascript
function showDealModal(dealId) {
  // 1. Create overlay + panel divs
  // 2. Fetch /api/deals/{dealId}
  // 3. Populate: stage badge, value, industry, contact, notes, timeline
  // 4. "Edit Deal" button → closeDealModal(); showDealDetail(id)
  // 5. Click overlay or close button → closeDealModal()
}
```

Panel CSS:
```css
.deal-slide-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.25); z-index: 999; backdrop-filter: blur(1px); }
.deal-slide-panel { position: fixed; top: 0; right: 0; width: 480px; max-width: 90vw; height: 100%; background: #fff; box-shadow: -8px 0 30px rgba(0,0,0,0.08); z-index: 1000; display: flex; flex-direction: column; overflow-y: auto; animation: slideIn 0.2s ease; }
@keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
```

## User Preferences (Greg)

- **All text #111 black** — no muted grays on the kanban board (headers, empty states, chips, add buttons, value badges). User explicitly requested "all the text on the deal page kanban in black."
- **Uniform header borders** — all stage headers must have the same bottom-border position regardless of name length (use `white-space: nowrap` + 9px font)
- **No horizontal scrolling** — all stages visible at once at 1280px
- **Vertical stack** — chips always stack one-per-row, never side-by-side, never wrapping horizontally
- **Dynamic column widths** — columns should size to their content (longer names get more room), not be equal-width
- **Compact** — small chips, minimal padding, lean aesthetic
- **Hash routing** — every page must have a URL hash so refresh lands on the right page
