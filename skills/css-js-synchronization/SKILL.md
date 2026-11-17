---
name: css-js-synchronization
description: "Prevent alignment bugs between CSS layout values and JS calculations by reading rendered DOM measurements instead of hardcoding magic numbers."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [css, js, alignment, layout, dom, rendering, quality]
---

# CSS ↔ JS Synchronization

## When This Fires

Load this skill whenever you:
- Change CSS layout properties (heights, widths, positions) that have corresponding JS calculation constants
- Build a calendar, timeline, grid, or any component with JS-positioned overlay elements
- Refactor styling on a page that has JS-driven positioning (blocks, cards, overlays, annotations)
- See or suspect misalignment between rendered elements and their calculated positions

## Core Pattern

**Never hardcode a layout value in JS that is defined in CSS.**

Instead, read the actual rendered value from the DOM at render time:

```js
// ❌ BAD — magic number, drifts when CSS changes
const rowHeight = 32;
const ppm = rowHeight / 15;

// ✅ GOOD — reads actual rendered height
const firstRow = grid.querySelector('.time-row');
const rowHeight = firstRow ? firstRow.offsetHeight : 36; // 36 = safe fallback
const ppm = rowHeight / 15;
```

## Why This Gets Missed (the failure chain)

1. **CSS and JS are authored in the same file but treated as separate concerns.** During a theme/visual refactor, heights, colors, and spacing are changed in the CSS block while the JS logic section below remains untouched.
2. **No cross-reference check.** The developer (or agent) changes `.time-row { height: 36px }` but never checks if a JS constant like `const rowHeight = 32` exists downstream.
3. **The bug is invisible at a glance.** The page loads, blocks render, text is visible — nothing crashes. The misalignment only becomes apparent when you carefully compare block edges against grid lines.
4. **Mobile vs desktop further masks it.** The CSS has a media query with a different height (32px on mobile), which happens to match the old hardcoded value — making testing ambiguous.

## Checklist During CSS Refactors

Before pushing any CSS change that touches dimensions:

- [ ] Search the JS for any hardcoded pixel/position constants that reference the same elements
- [ ] Replace hardcoded constants with DOM reads (`element.offsetHeight`, `element.offsetWidth`, `getBoundingClientRect()`)
- [ ] If DOM reads aren't possible (element not rendered yet), use `getComputedStyle()` on a template or a CSS variable reference
- [ ] Test the alignment at all responsive breakpoints by rendering actual content, not just verifying no JS errors

## When You Can't Read the DOM

If the element isn't rendered yet when you need the value:

```js
// Option A: Render first, measure after
container.innerHTML = '<div class="time-row"></div>';
const h = container.querySelector('.time-row').offsetHeight;
container.innerHTML = ''; // clear template

// Option B: Read from computed style of a CSS class
const tmp = document.createElement('div');
tmp.className = 'time-row';
tmp.style.position = 'absolute'; tmp.style.visibility = 'hidden';
document.body.appendChild(tmp);
const h = tmp.offsetHeight;
document.body.removeChild(tmp);
```

## Verifying Alignment

After any layout change:

1. Open the page in a browser
2. Render real content in the view (e.g., click a day in the calendar)
3. **Visually check** that block edges line up with grid row boundaries
4. Scroll through all hours, not just the top
5. Check at mobile viewport width too

## Production Pitfalls

### 1. Pseudo-elements for grid lines drift separately
If you use `::after` to draw timeline grid lines, that pseudo-element's positioning is in CSS, not JS — yet it must match the JS overlay's coordinate system. When you change row height in a media query, the pseudo-element's `left` and `top` must update too. Easy to miss because both are in CSS but in different rule blocks.

✅ Fix with a shared CSS variable:
```css
.time-grid { --label-width: 54px; }
.time-row.half-hour::after { left: var(--label-width); }
.blocks-overlay { left: var(--label-width); }
.now-line { left: var(--label-width); }
```

### 2. Stale comments that lie
A comment like `// matches CSS height: 32px` next to a hardcoded JS constant traps future you — it makes the code look maintained when it's actually stale. If you can't read from the DOM, remove the misleading comment and flag the risk.

### 3. Visual verification catches what silent loads miss
Structural checks ("page loads, no JS errors, month grid visible") catch crashes but not alignment bugs. After any dimension/position change: open the content view, compare block edges against grid lines at the top, middle, and bottom of the scroll range, and check every responsive breakpoint. A 16px/hour drift is invisible until you check the 10th row.

### 4. Responsive breakpoints multiply the failure surface
A media query changing `.time-row { height: 16px }` on mobile while desktop is 18px means `offsetHeight` auto-corrects — but only if read *after* the media query activates. Reading dimensions in `init()` before the viewport triggers the breakpoint caches the wrong value. Always read dimensions at render time, not init time.

### 5. The overlay chain shares a coordinate system
Four elements share the same horizontal origin in a timeline: **time labels** (define column width), **blocks overlay**, **now-line**, and **grid-line pseudo-elements**. If any uses a different `left` value, nothing crashes but everything misaligns. A single `--label-width` variable linking all four prevents the entire class of bug.

### 6. innerHTML script tags never execute
Browsers refuse to run script tags inserted via innerHTML — W3C security spec. Any dynamic script injection is silently ignored. Fix: call the function directly after the innerHTML assignment.
When using data attributes in HTML and closest() in the click handler, the attribute names must be character-for-character identical. A mismatch (e.g., HTML uses data-lid but click handler queries closest([data-idx])) silently returns null on every click - the dropdown opens, items render, but nothing happens. No console errors.
Prevention: After writing event delegation code, grep for both the HTML attribute name AND the closest() selector to confirm they match.
Browsers refuse to run `<script>` tags inserted via `innerHTML` — W3C security spec. Any dynamic script injection is silently ignored. Fix: call the function directly after the innerHTML assignment:
```js
// WRONG — dead code, never executes
cp.innerHTML = '...<script>loadActionsForLead("' + id + '")</script>';

// RIGHT — call after rendering
cp.innerHTML = '...';
loadActionsForLead(id);
```

### 7. innerHTML onclick escaping → data-attributes
Using `\'` to escape quotes inside onclick attributes in innerHTML strings fails because the HTML parser un-escapes before JS evaluation. The `\'` that was intended as a JS string delimiter becomes a raw `'` that closes the HTML attribute. Fix: never inline onclick with string arguments in innerHTML. Use `data-*` attributes + `this.dataset`:
```js
// WRONG — broken by HTML/JS escaping layers
'<button onclick="func(\'' + id + '\')">Click</button>'

// RIGHT — data attributes survive all parsing layers
'<button data-id="' + id + '" onclick="func(this.dataset.id)">Click</button>'

### 8. Event delegation selector must match data-attribute name exactly
When using data attributes in HTML and closest() in the click handler, the attribute names must be character-for-character identical. A mismatch (e.g., HTML uses data-lid but click handler queries closest([data-idx])) silently returns null on every click — the dropdown opens, items render, but nothing happens. No console errors.
Prevention: After writing event delegation code, grep for both the HTML attribute name AND the closest() selector to confirm they match.
```
