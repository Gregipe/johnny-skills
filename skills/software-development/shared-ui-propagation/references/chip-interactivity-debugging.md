# Chip (Radio Button) Interactivity Debugging — May 2026

When tone/language chips in the Prompt Builder don't respond to clicks, or the visual selection doesn't update:

## Failure 1: Hidden Radio Inputs Break Label Clicks

**CSS:** `.pb-chip input { display:none; }`

The `<label>` wraps an `<input type="radio">`, but `display:none` on the radio can prevent click forwarding in some browsers. Browsers differ in how they handle label clicks when the labeled input is `display:none`.

**Fix:** Replace `display:none` with visual hiding that keeps the element in the accessibility/interaction tree:

```css
/* BROKEN — breaks label click forwarding in some browsers */
.pb-chip input { display:none; }

/* FIXED — visually hides but keeps label→input interaction */
.pb-chip input { opacity:0; position:absolute; width:0; height:0; pointer-events:none; }
```

**Verification:**
```javascript
var radio = document.querySelector('.pb-chip input');
getComputedStyle(radio).display; // must NOT be "none"
```

## Failure 2: Programmatic Check Without Visual Class Update

When the prefill runs `toneEl.checked = true`, the radio IS selected but the CSS `selected` class on the label chip is NOT updated. The chip still shows the old visual state (border style from another chip that still has `selected`).

**Fix:** After setting `checked = true`, also update the CSS classes:

```javascript
// When pre-filling a chip programmatically:
if (toneEl) {
  toneEl.checked = true;
  // Update visual state
  var chips = pb.querySelectorAll('#pe_tone_chips .pb-chip');
  chips.forEach(function(c) { c.classList.remove('selected'); });
  toneEl.closest('.pb-chip').classList.add('selected');
}
```

Same pattern for language chips or any radio-button chip group.

## Failure 3: No Click Handler to Update Visual State

When a user clicks a chip, the browser correctly checks the radio (label→input behavior), but no JavaScript updates the `selected` CSS class. The old chip still looks selected because its label still has the `selected` class.

**Fix:** Add a delegated click handler that updates the visual state on every chip click:

```javascript
document.addEventListener('click', function(e) {
  var chipGroup = e.target.closest('.pb-chips');
  if (chipGroup && e.target.closest('.pb-chip')) {
    chipGroup.querySelectorAll('.pb-chip').forEach(function(c) {
      c.classList.remove('selected');
    });
    e.target.closest('.pb-chip').classList.add('selected');
  }
});
```

This goes in the same delegated event handler as other click handlers (sidebar nav, module card toggles, etc.).

## Verification

```javascript
// Click each chip and verify:
var pb = document.getElementById('pbOverlay');
pb.querySelector('#pe_tone_chips input[value="warm"]').closest('.pb-chip').click();
var checked = pb.querySelector('#pe_tone_chips input:checked');
console.log('Checked:', checked?.value, '| Has selected class:', checked?.closest('.pb-chip')?.classList.contains('selected'));
// Expected: Checked: warm | Has selected class: true
```
