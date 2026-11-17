---
name: web-calculator-microtools
description: "Turn spreadsheet models into interactive web calculators."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [calculator, web, cloudflare-workers, spreadsheet, roi, hunar, static-site]
    category: software-development
---

# Web Calculator / Micro-Tool Skill

Build an interactive single-page calculator/micro-tool from a spreadsheet (or paper) cost/ROI model, verify the math reproduces the source, deploy to Cloudflare Workers, and iterate on the visual design. The worked example is Hunar's "Voice AI ROI Calculator" (break-even model for adding a Voice AI pre-screen to a telecalling funnel).

## When to Use

- Turning a Google Sheet / Excel cost model into a shareable web calculator.
- Building client-facing Hunar pitch tools (calculators, configurators, ROI/break-even pages).
- Any small static single-page app that needs a verified math core plus a polished UI.

## Design-First (Greg's rule)

Greg wants a design rundown BEFORE code. He said it directly: "before you build anything ask me your questions or run through the design once and we can then build." Sketch the segments, surface the real forks (theme, input types, ranges), and get sign-off before writing code. He will push for polish — a plain card grid reads as "blobs" to him.

Aesthetic defaults for financial/data tools (theme is a per-session fork — Greg has flipped dark↔light, so make it a one-variable swap, not a rewrite):
- **Dark premium**: near-black canvas, elevated cards, ONE accent color with a glow. **White premium** (landed state for the Voice AI calculator): warm off-white canvas `#FBF9F7`, white cards, ONE accent. In both, keep a single accent color.
- **Match the reference site Greg points at** — extract its exact typography and colors (see "Design-token extraction" below), don't guess.
- **Sliders** (custom-styled thumb + filled track) for ranged inputs; show the live value as **plain text beside the slider, hugging it** (auto-width chip, ~4px gap) — NOT a colored chip/oval, and not a wide fixed slot that floats the value far right of the track. Keep money fields as ₹ text boxes unless he specifies a slider range.
- **Numbered, clearly-separated segments** (`1 · X`, `2 · Y`, …) when a page has multiple input/output groups; put them in a grid so they're equal width (2×2 for four segments).
- **Big colored headline number** for the key result (e.g. the ROI %).

## Prerequisites

- Node 22 (`npx`).
- Cloudflare `wrangler` authenticated — `npx --yes wrangler whoami` (OAuth token lives in `~/Library/Preferences/.wrangler/config/default.toml`).
- The source model's numbers (or the sheet itself) to verify against.

## How to Run

1. **Read the source model.** For a public Google Sheet, fetch CSV directly (see reference).
2. **Put ALL math in a pure ESM module** (`public/calc.js`) — `export function compute(inputs)` returning a plain object, plus `export` format helpers (`inr`, `pct`, `mult`). The browser imports it via `<script type="module">`; a Node `.mjs` test imports the *same file*.
3. **Write a Node test** asserting the module reproduces known source values EXACTLY, plus sensitivity and edge cases. Run `node test.mjs` before any UI work.
4. **Build a single-file `public/index.html`** (no framework) importing calc.js; wire inputs/sliders to a `render()`.
5. **Verify in a real browser**: `browser_navigate` + `browser_console` — read computed DOM textContent, assert zero JS errors, and drive inputs with `el.value = x; el.dispatchEvent(new Event('input', {bubbles:true}))`. The accessibility snapshot may omit result text — read via `getElementById(...).textContent`.
6. **Deploy** as Cloudflare Workers static assets (wrangler.jsonc + passthrough worker — exact files in the reference). Local: `npx --yes wrangler dev --port 8787` (background) then verify with `lsof -nP -iTCP:8787 -sTCP:LISTEN` + curl. Production: `npx --yes wrangler deploy`.

## Design-token extraction (match a reference site)

When Greg says "keep the fonts/sizes as per <site>", extract them instead of eyeballing:
- `browser_navigate` to the site, then `browser_console` reading `getComputedStyle`: `fontFamily`, `fontSize`, `fontWeight`, `letterSpacing`, `lineHeight` on h1/h2/h3/body/labels/buttons; `backgroundColor`/`color` (may be `oklch(...)` — copy the value verbatim into CSS; browsers accept oklch).
- **Cross-origin preview iframes** (Framer marketplace "Show Preview"): the iframe is `*.framer.app`, blocked from the parent — `browser_navigate` DIRECTLY to the preview host URL and inspect there.
- To verify a visual change when the vision model is unavailable, assert via `browser_console` on computed styles (bg color, font size/weight, element widths) and share the screenshot path back with `MEDIA:<path>` so Greg reviews it himself.

## Reading a layout mockup (Google Slides)

Greg sometimes hands over the target layout as a Google Slides deck of pasted screenshots — he screenshots the current build and rearranges the pieces on a slide. The deck is public ("anyone with the link"), so read it programmatically instead of eyeballing:

1. Export PPTX — `curl -sL "https://docs.google.com/presentation/d/<ID>/export/pptx" -o deck.pptx`.
2. Read geometry — `ppt/slides/slide1.xml` holds each screenshot as `<p:pic>` with `<a:off x="…" y="…"/><a:ext cx="…" cy="…"/>` in EMU (914400 EMU = 1 inch); map `r:embed` rIds to `ppt/media/imageN.png` via `ppt/slides/_rels/slide1.xml.rels`. x/y/width/height reveal the intended grid (columns, stacked panels, full-width strip).
3. OCR the screenshots — they have no text layer, and `vision_analyze`/`browser_vision` may not attach images in a session. Use `scripts/ocr_image.swift` (macOS Vision): `swiftc -O scripts/ocr_image.swift -o ocr && ./ocr <image.png>` — prints each line with its normalized bounding box, sorted top-to-bottom, so you can reconstruct the layout without literally seeing it.
4. Confirm the interpretation — a slide of screenshots is inherently ambiguous (a wide crop can mean "full-width strip" or "card header band"). State your reading and `clarify` with concrete options before rebuilding.

Worked example (the Voice AI calculator deck) is in `references/layout-mockup-extraction.md`.

## Pitfalls

- **Never hand-reimplement the math in the test** — import the SHIPPED module so you test what actually ships.
- **Break-even solving with N levers is underdetermined** (1 equation, N unknowns). Solve each lever individually holding the others at their current values, flag ">100% / not achievable alone", and add a composite "required end-to-end conversion" as the real benchmark.
- **Rounded display vs unrounded compute**: compute with unrounded intermediates so cost-per-conversion matches the sheet (the sheet shows "4 conversions" but divides by 4.158).
- **Sign semantics**: an "ROI-negative" result is a cost *increase* — display `−X%`, not `+X%`.
- **Google Sheet gid probing**: non-existent gids return HTML (not CSV) at ~8 KB — check content, don't assume multiple tabs.
- **Wrangler `dev` runs silently** — no "Ready" log line even when the server is fine; verify readiness with `lsof` + `curl`, never by waiting for output.
- **Equal-width grid columns drift** — `grid-template-columns: 1fr 1fr 1fr` still sizes each track as `minmax(auto, 1fr)`, so an unbreakable child (long `white-space:nowrap` label/chip) inflates one column and the others shrink (observed 357/347/347 px). Add `> *{min-width:0}` to the grid — and to any `repeat(n,1fr)` strip — to force true equal tracks. Verify with `browser_console` reading `getBoundingClientRect().width` on each grid child.
- **Equal-height sibling cards.** Greg asks for adjacent segment cards to be the SAME size (width *and* height). `align-items:start` on the grid sizes each card to its own content (an input card with fewer fields is shorter than the output card); drop it (grid default `stretch`) so all cards in a row share the tallest card's height. Verify with `getBoundingClientRect().height` on each `.card`.
- **Audit inputs for semantic duplicates before exposing them.** Greg will flag two fields that are "logically the same thing" — e.g. a human call-connectivity that appears twice (once for the before path, once for the after path) because the source sheet had two cells. Same underlying metric → ONE input shared by both paths. Merging is cheap in a pure `compute()` (one `frac()` instead of two, same value substituted into both equations); leaving duplicates in reads as a modelling smell and Greg will call it out.
- **Horizontal input strips (label + value chip + slider per column) lose vertical alignment** when labels wrap to different line counts — chips float at different heights and sliders land on different rows ("stamping all over each other"). Don't fix it with `flex:1` on the label zone inside a stretched grid item: Chrome resolves that flex-grow *circularly* and one column ends up taller than the row (observed 130px vs 108px, labels misaligned by 20px steps). The verified fix is a rigid 2-layer field stack with NO flex-grow and NO line-clamp:
  - **Label zone** `min-height:66px` (3 × 22px lines), `display:flex; align-items:flex-end` so 1- and 2-line labels bottom-align with 3-line ones. Use `min-height`, NOT `height` + `-webkit-line-clamp`/`overflow:hidden` — clamping silently truncates load-bearing labels (e.g. "(on raw leads)" vs "(human → AI-screened leads)") on a font-fallback frame or a one-word copy edit.
  - **Control row** `.srow` `display:flex; align-items:center; gap:4px; min-height:42px` — slider `flex:1; min-width:0` and the value in a plain auto-width chip (`.srow .chip{flex:none;width:auto;text-align:right}`) so it hugs the slider like a unit suffix. The guardrails that matter are the slider's `flex:1;min-width:0` (track keeps full width) and the chip's `flex:none` (never steals track space) — with those, an auto-width chip does NOT collapse sliders. The failure mode that LOOKS broken is a *fixed-width right-aligned slot* (64px): `text-align:right` inside a fixed box puts the dead space to the LEFT of the text, so "30%" renders ~39px from the slider edge and Greg reads the value as floating — he asked twice to move it closer and only accepted it once the text actually hugged the track. Trade-off: hugging chips end at different x positions per row; if he ever wants right-edge column alignment back, offer a capped width (`min-width:44px; width:auto`), don't auto-apply it. (An earlier iteration put the chip *below* the slider `align-self:flex-end` for full-width sliders — Greg rejected it: "text coming below the slider", "not all aligned". He wants the value on the SAME line as its slider.)
  - **Labels carry unit/explainer subtext and sit tight on their slider.** Greg iterates labels until they are self-explanatory: percentage metrics get `(%)`, qualified ones `(%, on connected leads)`, and long explainers go inline in the `.unit` span (e.g. `(for eg. human conversion becomes 60% from a baseline of 20% at 3X - pre-screened leads convert better)`) — let them wrap naturally, don't shrink the font. The label row sits ~4px above its slider (`.flabel{margin-bottom:4px}`; the strip label zone keeps only the `min-height` needed for cross-field bottom alignment) — a 10px+ gap reads as floating. When adding a subtext, mirror the exact capitalization and punctuation Greg typed; he notices deviations.
  - **Values are plain ink text, not a pill**: `color:var(--ink); font-weight:600; font-variant-numeric:tabular-nums`. Greg called the blue oval noise ("maybe we don't need a blue oval necessarily") — when he offers a "take a call", the minimal/plain option is what he wants.
  - Scope-override `input[type=range]{margin:0}` inside `.srow` — a global `margin:8px 0 4px` leaks an ~8px offset between the ₹ textbox row and slider rows. Match the CPL textbox band with `padding:8px 0` on its input (both land at 42px).
  - Keep the `min-height:66px` zone at the 2-col breakpoint (dropping it misaligns 1-line vs 2-line labels by 22px in the same grid row); only release below 640px (single column, no shared baseline).
  - Verify by asserting all chips share one `getBoundingClientRect().y`, all sliders share one `y`, and the ₹ textbox row top equals the slider row top.
- **For a layout/visual bug, delegate a measurement pass.** Dispatch a leaf subagent (`delegate_task`, toolsets `web,file,terminal`) pointed at the file, asking it to drive headless Chromium (Playwright) at many viewports and return concrete CSS + measured geometry (overlap / band-spread / clip). It catches what eyeballing misses (chip-beside-slider collapsing sliders to 73px, clamp truncation). Require "analysis only, do not edit files" so it can't fight your own concurrent edits.

## Verification

- `node test.mjs` passes reproduction + sensitivity + edge cases.
- Browser: zero JS errors; values match expected; interaction flips verdict/targets.
- Production: the workers.dev URL returns 200 and contains the expected markers (`type="range"`, result element ids).
- **Gap checks on the live DOM** (when the vision model can't see screenshots): label-bottom → slider-top ≈ 4px; slider-right → chip-TEXT-left ≈ 4px. Measure the chip text with `document.createRange()` + `range.getBoundingClientRect()` on the chip's contents — the chip BOX is wider than the text when right-aligned, so box-edge measurements lie about the visual gap.

## Quick Reference

| Task | Command |
|---|---|
| Check wrangler auth | `npx --yes wrangler whoami` |
| Local serve | `npx --yes wrangler dev --port 8787` (background) |
| Deploy | `npx --yes wrangler deploy` |
| Test math | `node test.mjs` |
| Sheet CSV | `curl -sL "…/export?format=csv&gid=0"` |

See `references/hunar-roi-calculator.md` for the worked model (formulas + verified values), the dark AND white design tokens, Hunar brand colors, and the exact Cloudflare worker files. See `references/layout-mockup-extraction.md` + `scripts/ocr_image.swift` for reading a Google Slides layout mockup when the vision model can't see it.
