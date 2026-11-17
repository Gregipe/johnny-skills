# Hunar.ai brand palette (canonical)

Extracted from live computed styles on hunar.ai (Framer site) + logo decode, Sep 2026.
Use these when a page must be "in Hunar colors" but not Hunar-logo-branded
(e.g. a neutral calculator or tool that carries Hunar only in the About/footer).

## Colors

| Role | Hex | Notes |
|------|-----|-------|
| Primary brand blue | `#006EDD` | CTA buttons, links (computed `rgb(0,110,221)`) |
| Light accent | `#369BFF` | gradients / hover / secondary (`rgb(54,155,255)`) |
| Ink (headings/text) | `#121212` | primary text; headings also render `#1a1a1a` |
| Muted text | `#717171` | secondary/captions |
| Canvas | `#FAFAF9` | page background |
| Card border | `#EDEDED` | hairline borders on white cards |
| Blue tint (fills) | `rgba(0,110,221,.07)` | soft highlight fills |
| Positive/negative | `#16A34A` / `#DC2626` | semantic status only (verdict chips, bars) |

## Logo

Hunar's wordmark is **monochrome** — dominant pixel `#15191e` (near-black, cool tint)
with grays (`#686b6d`, `#32363a`). Do NOT derive the brand accent from the logo; derive
it from computed button/link styles on the live site instead.

## Font

Site uses Geist (Vercel). `Inter` from Google Fonts is the closest safe substitute for a
no-build single-file page. Use `font-variant-numeric: tabular-nums` on figures.

## How to extract (repeatable)

1. `browser_navigate https://www.hunar.ai`, then `browser_console` with a probe that
   walks `getComputedStyle` collecting (a) non-neutral `backgroundColor`s and
   (b) non-gray/non-default-blue `color`s. The brand blue surfaces as CTA backgrounds
   and link color; the light accent as gradients/hover states.
2. For a logo or screenshot, run `scripts/png_dominant_colors.py <file.png>` (pure
   Python stdlib, no PIL) to get dominant non-white colors.
