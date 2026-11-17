# Reading a Google Slides layout mockup (worked example)

When Greg wants a layout change he sometimes sends a Google Slides deck
(`docs.google.com/presentation/d/<ID>/edit`) where he screenshots the current build
and rearranges the pieces into the target layout. The deck is "anyone with the link",
so read it programmatically instead of guessing from a thumbnail.

## Steps

1. **Export PPTX** — `curl -sL "https://docs.google.com/presentation/d/<ID>/export/pptx" -o deck.pptx`
2. **Read geometry** — unzip, then `ppt/slides/slide1.xml` holds each pasted screenshot as
   `<p:pic>` with `<a:off x="…" y="…"/><a:ext cx="…" cy="…"/>` in EMU (914400 EMU = 1 inch).
   Map `r:embed="rIdN"` → `ppt/media/imageN.png` via `ppt/slides/_rels/slide1.xml.rels`.
   x/y/width/height reveal the intended grid (columns, stacked panels, full-width strip).
3. **OCR each PNG** — the screenshots have no text layer, and `vision_analyze` /
   `browser_vision` may not attach images in a session. `scripts/ocr_image.swift`
   (macOS Vision) prints `[x,y width%] text` sorted top-to-bottom.
4. **Confirm the ambiguous reading** — state your interpretation and `clarify` with concrete
   options before rebuilding. A slide of screenshots is inherently ambiguous.

## Worked example (Voice AI ROI calculator, 2026-09)

Slide (16:9 = 12192000 × 6858000 EMU) held 5 images:

| file      | x        | y        | w        | h        | content |
|-----------|----------|----------|----------|----------|---------|
| image1.png| 207696   | 234601   | 3048700  | 930150   | wide horizontal crop (~3.33"×1.02") of segment 1's top (title + hint + CPL field) |
| image2.png| 59225    | 152400   | 3247300  | 4730201  | left column — full "1 Customer Status Quo" card |
| image3.png| 3441612  | 152400   | 2993900  | 2214351  | middle-top "2 VoiceAI Input Metrics" |
| image4.png| 3441612  | 2405050  | 2993899  | 2525050  | middle-bottom "3 VoiceAI Output Metrics" |
| image5.png| 6541333  | 152400   | 3247305  | 4777699  | right column "4 ROI" |

OCR (via the Swift script) recovered each card's title / fields / values, e.g.
`[12,4 8w] ROI`, `[9,19 64w] -35.1%`, `[9,53 35w] R1,833.33` (note: the `₹` glyph
OCRs as `R`, and `AI` often comes back as `Al`).

**Interpretation**: a full-width top strip (the wide crop = "Customer Status Quo"
stretched wide with its fields laid out horizontally) over three equal columns
(VoiceAI Input | VoiceAI Output | ROI). Confirmed via `clarify` (3 options) because
a wide crop is ambiguous between "full-width strip" and "card header band".

## The equal-width grid fix (separate but adjacent lesson)

After rebuilding as a top strip + `grid-template-columns:1fr 1fr 1fr`, the three
columns measured 357/347/347 px instead of equal. Cause: `1fr` tracks are
`minmax(auto, 1fr)`; an unbreakable descendant (long nowrap label/chip) inflated
track 1 and shrank the others. Fix:

```css
.seggrid > *{min-width:0}   /* and for the 5-col strip: .stripgrid > *{min-width:0} */
```

Result: 351/351/351 columns, and the 5-field strip 192/192/192/192/192. Verify
equality with `browser_console` reading `getBoundingClientRect().width` on each grid
child — don't trust the eye.
