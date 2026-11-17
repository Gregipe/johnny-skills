# Drag-Drop Step Reorder — HTML5 Native Drag API

Implementation used in the Outreach Central cadence builder for reordering step cards.

## Setup

Each draggable card needs:
```html
<div class="step-card" data-step-index="0" data-action="select-step" draggable="true" data-drag="step">
  <span class="drag-handle" data-drag-handle="0">⠿</span>
  ...
</div>
```

- `draggable="true"` enables native HTML5 drag
- `data-drag="step"` identifies draggable elements for the delegated handlers
- `data-step-index` tracks current position (re-rendered after every reorder)
- `drag-handle` is optional but recommended — the `⠿` character gives a visual grab target

## CSS

```css
.drag-handle { font-size:13px; color:#C0C0C5; cursor:grab; flex-shrink:0; line-height:1; user-select:none; }
.drag-handle:active { cursor:grabbing; }
.step-card.dragging { opacity:0.4; border-color:#111; border-style:dashed; }
.step-card.drag-over { border-color:#2563eb; border-style:dashed; background:#F8FAFF; }
```

## Event Handlers

```javascript
var dragSrcIdx = -1;

document.addEventListener('dragstart', function(e) {
  var card = e.target.closest('[data-drag="step"]');
  if (!card) return;
  dragSrcIdx = parseInt(card.dataset.stepIndex);
  card.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', dragSrcIdx);
});

document.addEventListener('dragend', function(e) {
  var card = e.target.closest('[data-drag="step"]');
  if (card) card.classList.remove('dragging');
  document.querySelectorAll('.step-card.drag-over').forEach(function(c) { c.classList.remove('drag-over'); });
  dragSrcIdx = -1;
});

document.addEventListener('dragover', function(e) {
  var card = e.target.closest('[data-drag="step"]');
  if (!card || dragSrcIdx < 0) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  document.querySelectorAll('.step-card.drag-over').forEach(function(c) { c.classList.remove('drag-over'); });
  card.classList.add('drag-over');
});

document.addEventListener('drop', function(e) {
  var card = e.target.closest('[data-drag="step"]');
  if (!card || dragSrcIdx < 0) return;
  e.preventDefault();
  document.querySelectorAll('.step-card.drag-over').forEach(function(c) { c.classList.remove('drag-over'); });
  var targetIdx = parseInt(card.dataset.stepIndex);
  if (dragSrcIdx === targetIdx) return;
  // Reorder in data
  var t = getTemplate();
  if (!t || !t.steps) return;
  var step = t.steps.splice(dragSrcIdx, 1)[0];
  t.steps.splice(targetIdx, 0, step);
  // Normalize: ensure no step fires before a preceding step
  normalizeTimings();
  saveData();
  selectedStepIndex = targetIdx;
  renderSteps();
  // Reset preview state
  resetPreview();
  markUnsaved();
});
```

## Key Details

- `closest('[data-drag="step"]')` — uses data attribute, not class, so it works with re-renders
- `dataTransfer.setData()` — required for Firefox (Chrome works without it)
- `e.preventDefault()` on `dragover` — required to allow drop
- `dragend` fires even on dropped items — always reset `dragSrcIdx = -1`
- After reorder, `normalizeTimings()` is called to enforce the monotonic constraint: each step's cumulative time (`day*24 + delay`) must be >= the previous step's. Steps that would fire before their predecessor get bumped forward to match. Step 0 is always reset to Day 0·+0h. Unlike the old force-recalculate approach, user-set delays are preserved as long as they satisfy the constraint.
