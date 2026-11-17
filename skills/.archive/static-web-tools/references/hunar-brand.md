# Hunar.ai Brand Palette

Extracted from the live site (`www.hunar.ai`, a Framer app) and the logo PNG on 2026-09-23.
These are the colors to use when building Hunar-adjacent but *not* officially-branded tools
(Greg's instruction: "brand it broadly in the Hunar colors", neutral, with an About section
mentioning Hunar).

## Palette

| Role | Hex | Notes |
|------|-----|-------|
| Primary / CTA / links | `#006EDD` | brand blue; CTA buttons, tab-active, sheet-link |
| Light accent / hover | `#369BFF` | gradient partner to primary |
| Primary tint | `rgba(0,110,221,.07)` | section backgrounds / focus rings |
| Ink / headings | `#121212` | near-black; body text `#1a1a1a` |
| Canvas | `#FAFAF9` | page background |
| Muted / secondary text | `#717171` | hints, labels, footer |
| Border | `#EDEDED` | card borders (also `#DDDDDD` for input rows) |
| Success / negative / warn | `#16A34A` / `#DC2626` / `#B45309` | semantic status |

Font: **Inter** (Google Fonts) 400–800 with `font-variant-numeric: tabular-nums` for figures.
Card style: white bg, 1px `#EDEDED` border, 16px radius, `#FAFAF9` canvas behind.

## How it was found

- `curl -s https://www.hunar.ai` → `grep -oiE '#[0-9a-f]{6}'` gives mostly neutrals + the blue.
- `browser_console` `getComputedStyle` on CTA/headings returns browser-default blue / neutrals
  because Framer applies styles via classes/CSS vars that don't surface in a naive scan.
- The **logo** (`https://framerusercontent.com/images/cFizG501dDd1ecsc9PIRo7UKM.png`) is a
  237×48 8-bit colormap PNG and its dominant ink is `#15191e` (monochrome dark) — so the logo
  itself is grayscale; the *accent* color (`#006EDD`) comes from the site's CTA/stat elements.

## Cloudflare account

- `npx --yes wrangler whoami` → logged in with OAuth token, email `gregipe@gmail.com`,
  account name `Gregipe@gmail.com's Account`, account ID `efb9fa19faea35e312429557f191a5d5`.
- Workers subdomain: `*.gregipe-efb.workers.dev` (existing examples: `mondelez-india-agent`,
  `voiceai-roi`).

## Copy references

- **Hunar.ai positioning** (hero): "Voice AI and autonomous HR operations for sourcing,
  onboarding, engagement, retention, and everything in between."
- **Mondelez About copy** (reusable boilerplate for an "About Hunar" section): "Hunar.ai builds
  enterprise-grade voice AI agents that conduct natural, human-like conversations at scale …
  fine-tuned for Indian languages and code-mixed conversations (Hinglish, Tanglish, etc.) …
  sub-second latency … integrates with existing CRM, telephony, and data systems — deployable
  in days." Capabilities list: multilingual voice agents, sub-second latency, SIP/PSTN/WebRTC
  telephony, voice cloning & persona design, real-time analytics.
