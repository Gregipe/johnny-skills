# Hunar Voice AI ROI Calculator — worked reference

## The model (per-lead, scale-invariant)

Inputs: marketing CPL `C`, telecaller CTC `M`, human call connectivity `hc` (a SINGLE value applied to both paths — Greg merged the sheet's two "connectivity" cells into one input), human conversion `cr`, AI cost/min `a`, AI AHT `t`, AI connectivity `ac`, AI engagement `ae`, interested disposition `ad`, productivity factor `f`.

Fixed model constants: `workDays = 25`, `connectsPerHumanDay = 30` (human capacity). Daily human cost `H = M/25`. Human cost scales proportionally with connected calls (`connects/30 × H`).

**Before AI (human-only):**
```
conv = hc·cr
humanCost = (hc/30)·H
cpcBefore = (C + humanCost) / conv
```

**After AI (Voice AI pre-screen + human on warm leads):**
```
e2e = ac·ae·ad·hc·cr·f        # end-to-end conversion per raw lead
aiCost = ac·t·a                 # billed only on connected calls
humanCost = (ac·ae·ad·hc / 30)·H
cpcAfter = (C + aiCost + humanCost) / e2e
```

Verdict: `positive = cpcAfter < cpcBefore`. `deltaPct = (cpcAfter - cpcBefore)/cpcBefore × 100`.

## Break-even closed forms (each lever solved alone, others held at current values)

Let `B = cpcBefore`:
```
ac* = C / [ B·ae·ad·hc·cr·f − t·a − ae·ad·hc·(H/30) ]
ae* = (C + ac·t·a) / [ ac·ad·hc·(B·cr·f − H/30) ]
ad* = (C + ac·t·a) / [ ac·ae·hc·(B·cr·f − H/30) ]
f*  = (C + ac·t·a + ac·ae·ad·hc·(H/30)) / [ B·ac·ae·ad·hc·cr ]
reqEndToEnd = (C + ac·t·a + ac·ae·ad·hc·(H/30)) / B   # AI path must convert ≥ this to break even
```
If a denominator ≤ 0, that lever cannot reach break-even alone (`Infinity`). A result > 100% means "not achievable via this lever alone". `reqEndToEnd` is the composite benchmark — the "number that decides it".

## Verified values at sheet defaults

`C=100, M=25000, hc=0.30, cr=0.20, a=3, t=1, ac=0.70, ae=0.55, ad=0.60, f=3`:
- cpcBefore = ₹1,833.33 · cpcAfter = ₹2,511.06 → verdict negative, delta +37.0%
- break-even: connectivity **97.5%**, engagement **76.0%**, disposition **82.9%**, productivity **4.1×**
- required end-to-end **5.7%** vs AI-path today 4.16% vs human-only 6.0%

Sensitivity sanity: raising human call connectivity 30→50% lowers BOTH cpcBefore and cpcAfter (it feeds both paths); raising engagement 55→90% flips the verdict positive (cpcAfter → ₹1,556.14).

## Google Sheet CSV export (public sheets only)

```bash
curl -sL "https://docs.google.com/spreadsheets/d/<id>/export?format=csv&gid=0"
```
Non-existent gids return HTML (~8 KB), not CSV — verify with `file` or by checking for `<!DOCTYPE`. Public sheets need no auth; private sheets need a token or `web_extract`/browser.

## Cloudflare Worker static-asset files (minimal passthrough)

`wrangler.jsonc`:
```jsonc
{
  "name": "voiceai-roi",
  "compatibility_date": "2025-09-27",
  "main": "src/index.js",
  "assets": { "directory": "public", "binding": "ASSETS" },
  "compatibility_flags": ["nodejs_compat"]
}
```
`src/index.js`:
```js
export default {
  async fetch(request, env) {
    try { return await env.ASSETS.fetch(request); }
    catch { return new Response("Not found", { status: 404 }); }
  },
};
```
Deploy → `https://<name>.<account-subdomain>.workers.dev` (Greg's subdomain: `gregipe-efb`).

## Hunar brand colors

- Primary blue `#006EDD` · bright accent `#369BFF` · ink `#121212` · canvas `#FAFAF9`.
- The logo is monochrome dark (`#15191e`) — do NOT trust the logo for the accent color.
- hunar.ai is Framer-built; computed styles show mostly neutrals. Extract real accent via `browser_console` scanning non-neutral backgrounds / accent text (`getComputedStyle`), not from the raw CSS.

## Dark premium design tokens (Vraxis Yield reference — Framer "Investment ROI Card")

- Canvas `#060606` · card `#0E0E12` · text `#F5F5F5` · muted `#A1A1AA` · faint `#71717A`.
- Border `rgba(255,255,255,.08)`. Gain `#10B981` · loss `#F87171` · ROI/amber callout `#FFAA00`.
- Sliders: 6px track `rgba(255,255,255,.12)`, 18px round thumb in accent with glow, white value chip above.
- Ratio bars: 8px, gray track + colored fill.
- Big headline number ~52px/800 for the key result.

## White premium design tokens (final landed state — Meldmint reference, meldmint-8.polsia.io)

Greg moved the calculator to white and asked to keep Meldmint's fonts/sizes. Extracted from the live site:

- Canvas `#FBF9F7` (warm off-white, `oklch(0.99 0.004 28)`) · card `#FFFFFF` · ink `#211E1B` (`oklch(0.18 0.01 28)`) · muted `#6F675F` · faint `#A39C93` · border `#ECE8E3`.
- Font **Inter** everywhere, weight **600** for all headings (Meldmint's signature — not 800).
- Type scale: page title 48px/600/`letter-spacing:-2.64px`/`line-height:60px`; segment h2 24px/600; body 16px/`line-height:24px`; labels 14px/600; buttons 14px/500 pill.
- **Display number** (the ROI figure): 96px/600/`letter-spacing:-6.24px`/`line-height:94px` (→ ~56px on mobile).
- Accent stays Hunar blue `#006EDD`/`#369BFF`; value chips become solid blue pills (white text). Verdict green `#0D9F63`, red `#D14343`, amber `#B45309`.
- Sliders: 6px track `rgba(0,0,0,.08)` (dark theme uses `rgba(255,255,255,.12)`); thumb 18px accent with white ring + soft shadow.

Note: Meldmint's own accent is a warm terracotta (`oklch(0.49 0.19 28)`); Greg said "fonts and sizes only", so keep Hunar blue unless he asks otherwise.

## Brand-extraction technique (no-dependency fallback)

When `PIL` is unavailable (e.g. arch mismatch on the machine), decode a paletted PNG with stdlib only: parse IHDR (width/height), PLTE (palette), IDAT (zlib-decompress), then apply PNG row filters (0/1/2). See the script pattern used this session for a ~30-line pure-python dominant-color extractor.
