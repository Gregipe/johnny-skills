---
name: elegant-web-design
description: Token-driven design system for calm, premium web pages.
version: 1.0.0
author: Greg
license: MIT
metadata.hermes.tags:
  - web-design
  - css
  - design-system
  - frontend
metadata.hermes.category: design
---

# Elegant Web Design Skill

A complete design system for building web pages that look like a strong product designer and a strong frontend engineer worked together. The page must feel **calm rather than busy, premium rather than decorative, deliberate rather than template-generated, spacious without feeling empty, visually rich without gradients/glassmorphism/gimmicks**, and polished at 1440px, 1024px, 768px, 390px, and 360px.

The agent makes ALL design decisions itself — never ask the user to choose fonts, card widths, spacing, radii, colors, breakpoints, or layout unless explicitly requested. Vague instructions ("make it elegant/premium/modern") are permission to apply this entire system.

## When to Use

- Building or restyling any web page: marketing landing pages, product pages, static tools, calculators, dashboards
- User asks for elegance, premium feel, "top startup" look, or a visual polish pass
- Before writing a single component of a new page

## Prerequisites

None — pure HTML/CSS guidance. Works with vanilla CSS or Tailwind (section 25). Use `browser_navigate` + `browser_console` for geometry measurement, and a headless-Chromium harness (Playwright/Puppeteer) for multi-viewport measurement when available.

## How to Run

One-shot generation workflow — execute in this order, internally:

1. **Identify the page story** — one sentence: "[Audience] has [problem]. This product provides [mechanism], resulting in [outcome]." Everything on the page supports it.
2. **Pick the visual personality** — one of: editorial / product-led / luxury / technical / playful / institutional / consumer.
3. **Lock design tokens** — background, surface, text, accent, radius, spacing, max widths, type scale. Do NOT change halfway through.
4. **Build hierarchy** — hero composition, section order, evidence placement, primary CTA, where product UI appears.
5. **Implement major geometry first** — width, spacing, columns, responsive stacking, section heights. Geometry matters more than decoration.
6. **Add type and color** — only after layout is sound.
7. **Add borders, shadows, icons, motion** — these are finishing layers.
8. **Run the quality gate** (below) before declaring done.

## Quick Reference

### Default tokens

```css
:root {
  --page-bg: #f6f7f4;
  --surface: #ffffff;
  --surface-soft: #f1f3ef;
  --surface-strong: #e9ece6;
  --text: #141814;
  --text-soft: #5f675f;
  --text-faint: #858d85;
  --line: rgba(20, 24, 20, 0.10);
  --line-strong: rgba(20, 24, 20, 0.16);
  --accent: #254f3d;            /* override to suit product */
  --accent-contrast: #ffffff;
  --accent-soft: #e6eee9;
  --success: #2f6d4b;
  --warning: #9a6818;
  --danger: #9b403d;
  --radius-xs: 8px; --radius-sm: 12px; --radius-md: 18px;
  --radius-lg: 24px; --radius-xl: 32px; --radius-pill: 999px;
  --shadow-xs: 0 1px 2px rgba(15,20,16,.05);
  --shadow-sm: 0 8px 30px rgba(15,20,16,.055);
  --shadow-md: 0 18px 60px rgba(15,20,16,.08);
  --page-max: 1240px; --content-max: 1080px; --copy-max: 720px;
  --s1:4px; --s2:8px; --s3:12px; --s4:16px; --s5:20px; --s6:24px;
  --s7:32px; --s8:40px; --s9:48px; --s10:64px; --s11:80px;
  --s12:96px; --s13:120px;
  --ease: cubic-bezier(.2,.8,.2,1); --fast:160ms; --medium:260ms;
}
```

**Token discipline:** never use random values (margin-top:37px, border-radius:13px, gap:27px) unless an exact reference forces it. Prefer the token scale — consistency creates perceived quality.

### Default recipe (when there is no reference)

Canvas `#F6F7F4` · text `#141814` · accent = deep green/ink/product hue · shell 1240px max (24px desktop gutters, 20px mobile) · hero 120px top spacing · sections 96–112px desktop / 68–76px mobile vertical padding · grid gap 20–24px · cards radius 24px, padding 28–32px desktop / 22–24px mobile, 1px black/10 border · buttons 48px height, 12px radius, 20px horizontal padding · body 16–18px/1.6 · section title 42–58px desktop / 34–42px mobile · shadows subtle, broad, low-opacity.

## Procedure

### Page width & horizontal rhythm (highest impact)

```css
.page-shell { width: min(calc(100% - 48px), 1240px); margin-inline: auto; }
@media (max-width: 640px) { .page-shell { width: calc(100% - 40px); } }
```

- Desktop shell 1180–1280px (default 1240); reading/copy width 640–760px; NEVER let paragraphs span the full viewport.
- Tablet ≤1024px: side padding 28–36px. Mobile ≤640px: 18–22px (default 20px).
- Important elements (logo, hero copy, headings, card groups, CTA, footer) align to one shared vertical line. No succession of unrelated centered blocks.

### Vertical spacing

- Compact section 64px; normal 88–104px; hero/major transition 112–144px. Mobile ~70% of desktop.
- Internal rhythm: eyebrow→heading 12–16px; heading→paragraph 20–28px; intro→content grid 40–56px; card title→body 10–16px. Whitespace is a design element — do not collapse everything together.

### Typography

- Stack: `Inter, "SF Pro Display", "SF Pro Text", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`. One high-quality family if remote fonts allowed (Inter, Geist, Manrope, DM Sans, Plus Jakarta Sans, Satoshi, Instrument Sans). Never mix 3 families. Editorial/premium: sans body + restrained serif display (Inter + Newsreader, Geist + Source Serif 4).
- Fluid scale: hero `clamp(3.2rem,6vw,6.4rem)/0.96/-0.055em/600`; section title `clamp(2.15rem,3.4vw,3.9rem)/1.02/-0.045em/600`; card title `1.15rem/1.25/-0.018em/600`; body-lg `clamp(1.05rem,1.2vw,1.25rem)/1.6`; body `1rem/1.62`; small `0.875rem/1.45`.
- Headings: tight line-height, slightly negative tracking, under 12 words, 1–2 lines on desktop. Body copy: max 620–720px, softened ink, 1.55–1.7 line-height, short paragraphs.
- No more than 4–5 visibly distinct text sizes in ordinary content.

### Color

- Ratio: ~70% neutral background, ~20% white surfaces, ~8% dark text, ~2% accent. One principal accent — no rainbow UI. Secondary colors ONLY for semantic states (success/warning/danger).
- No bright gradients across the page, no neon blobs, no purple/blue SaaS gradients, max 2 decorative background colors per viewport.
- Rhythm via subtle alternation: page neutral → white content area → accent-soft tinted section → neutral again. Don't band every section differently.

### Borders & shadows

- Default border: `1px solid rgba(20,24,20,.10)` — visible only when needed to define structure.
- Shadows sparingly; cards get a subtle border OR a soft shadow, rarely both strongly. Good: `0 12px 40px rgba(15,20,16,.06)`. Bad: `0 20px 80px rgba(0,0,0,.25)`. Premium design whispers structure.
- The page must still look elegant with all shadows removed — if not, geometry is weak.

### Cards

- Default: `background:var(--surface); border:1px solid var(--line); border-radius:var(--radius-lg); padding:28px`. Desktop padding: compact 20–24 / standard 28–32 / feature 36–48. Mobile 20–24.
- NEVER choose card widths individually — grid math: `.cards-3{grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}`, `.cards-2{repeat(2,minmax(0,1fr));gap:24px}`, asymmetric `.feature-grid{minmax(0,1.35fr) minmax(320px,.65fr)}`. Stack to 1fr below 860px — don't cram 3 cards across 700px.

### Section composition

5–8 major sections, not 15 tiny ones. Default sequence: Navigation → Hero → Product proof/mockup/live workflow → Problem→solution → Process → Outcome/audience → FAQ/proof → Final CTA → Footer. Interweave product UI and narrative rather than endless icon cards.

### Navigation

Height 72–84px, simple logo, max 3–5 links, 1 CTA (40–44px tall, 16–20px horizontal padding). Avoid boxed floating nav unless the direction calls for it. Mobile: hide low-priority links, keep logo + primary CTA/menu.

### Hero

Proportions: eyebrow → 14px → headline → 24px → supporting copy → 28px → CTA row → 40–64px → product proof. Hero content ~55–75vh before major proof. Headline max 800–1000px centered / 620–780px left-aligned — never edge-to-edge. CTA row: one primary (filled accent or dark ink, 44–52px), optional secondary that does NOT visually compete.

### Product UI inside marketing pages

Make mockups believable: realistic labels, actual statuses, timestamps, small metadata, compact chips, a few numbers, clear hierarchy. No Lorem ipsum, no generic icons, no decorative meaningless graphs. Slightly less dense than the real app: 12–14px metadata, 14–16px UI body, 16–18px panel headings, rows 44–56px.

### Chips, labels, statuses

Chips are for metadata, not decoration: `min-height:28px; padding:0 10px; border-radius:999px; background:var(--surface-soft); border:1px solid var(--line); font-size:12px; font-weight:600`. Status chips may use semantic tints. Never 5 chips around every heading.

### Buttons

`min-height:48px; padding-inline:20px; border-radius:12px; font-size:15px; font-weight:600` + 1–2px lift on hover. One dominant action per section; no giant pills; icons 16–18px; touch target ≥44px.

### Icons

One family (Lucide/Phosphor/Heroicons), stroke 1.5–2, size 18–22px. No emoji as production icons. Avoid oversized colored icon circles on every feature card — a classic template tell.

### Imagery

One strong image beats six mediocre ones; consistent crop treatment; intentional object-position; no generic stock. Image radius matches page geometry. Blank space is allowed — don't add imagery just to fill it.

### Responsive behavior

Responsive is not "desktop but narrower": columns stack, content reorders, decorative visuals simplify, nav collapses, card padding decreases, section spacing reduces, hero title scales fluidly. At 390px QA: no text clipping, no card wider than viewport, no 8px side padding, no buttons narrower than labels, no unreadable 10px copy, no orphan heading words. At 360px: no horizontal overflow at all.

### Motion

Allowed: 1–2px button lift, 4–8px card lift, opacity+translate reveal, subtle number/state transitions, accordion height/opacity, marquee when genuinely useful. `.reveal{opacity:0;transform:translateY(14px);transition:opacity 600ms var(--ease),transform 600ms var(--ease)}` → `.visible{opacity:1;transform:none}`. Avoid constant floating, bouncing icons, rotating gradients, parallax everywhere, slow 1.5s hovers. Always include `@media (prefers-reduced-motion: reduce){*{animation-duration:.01ms!important;transition-duration:.01ms!important}}`.

### Content-to-layout matching

Workflow-heavy → process rows, mini interface, timeline, status cards. Analytics-heavy → KPI tiles, chart preview, data table, annotation callouts. Trust-central → proof blocks, metrics, logos, quotes. Premium/high-ticket → fewer cards, more negative space, larger type, restrained copy. Technical → diagrams, code/architecture fragments, precise labels, spec blocks. Layout emerges from the product story.

### Anti-template rules

Do NOT use by reflex: purple-to-blue gradient, glassmorphism, glowing blobs, gradient text headline, icon-in-colored-circle on every feature, six equal feature cards, giant center-aligned everything, fake logo clouds, "Loved by teams worldwide", meaningless dashboard charts, excessive pill UI, different radius per component, alternating left/right image ×5, huge background words, dozens of micro-animations. One of these is OK when genuinely appropriate; never by reflex.

### Hierarchy & optical rules

Every viewport: primary message → supporting message → primary action → proof/product → secondary detail. If five elements shout at equal volume, the design is unfinished. Contrast via size/weight/spacing/grouping/position/muted color — never by adding more colors. Optical: bigger headings get stronger negative tracking; text in buttons may need 0.5–1px upward shift; judge visual weight, not computed dimensions (equal CSS heights can feel unequal with dense copy).

### Accessibility

Semantic HTML, visible focus states, keyboard navigation, sufficient contrast, meaningful button labels, alt text, correct heading hierarchy, motion-reduction support. Body 16px when possible; line-height ≥1.45; touch targets ≥44px.

### Implementation quality

Reusable components, CSS variables/design tokens, Grid/Flexbox over absolute positioning, responsive clamp(), semantic sections, limited nesting, no inline-style soup, no magic numbers, no duplicate CSS, no excessive dependencies.

### Tailwind equivalent (when project standard)

`<div class="mx-auto w-[calc(100%-40px)] max-w-[1240px] md:w-[calc(100%-64px)]">` · `<section class="py-20 md:py-24 lg:py-28">` · card `rounded-3xl border border-black/10 bg-white p-6 md:p-8`.

### Adaptation to references

When the user provides a reference URL/screenshot/brand: analyze page width, grid, section spacing, type scale, typography personality, background treatment, card radius, border opacity, shadow softness, accent usage, image treatment, product-UI density. Reproduce the design grammar, not the identity (no logos, proprietary illustrations, brand assets, exact text). If the reference is exceptionally polished, prefer its restraint and geometry over adding flourishes.

### Output requirements

Working complete code — no TODOs, real copy, no explaining basic CSS instead of implementing. If a preview/browser capability exists: render the page, inspect desktop, inspect mobile, correct spacing/wrapping/overflow issues, only then finish.

## Pitfalls

1. **Designing components before tokens** — random radii/spacings leak in component by component; lock tokens first, then never deviate.
2. **Decorating to look premium** — glowing blobs, gradient buttons, heavy shadows scream "template". If unsure, increase whitespace 10–20% instead of adding effects.
3. **Card widths chosen individually** — widths must derive from grid math (`minmax(0,1fr)`) or cards will drift out of alignment.
4. **Body copy spanning the viewport** — cap at 620–720px; wide paragraphs are the #1 "not designed" tell.
5. **Responsive = shrink** — mobile needs re-composition (stack, reorder, simplify), not just narrower columns; check 390px AND 360px for overflow.
6. **Rainbow UIs** — one accent; extra colors only for semantic states. Hierarchy via size/weight/spacing, not color count.
7. **Motion by reflex** — every animation must support hierarchy; always ship prefers-reduced-motion.
8. **Breakpoint stacking too late** — don't keep 3 columns at 700px; stack below ~860px.
9. **Missing focus states** — sliders, tabs, custom inputs need visible focus rings; elegance cannot cost usability.

## Verification (quality gate — page is NOT done until all pass)

- **Layout:** coherent max width; consistent gutters; intentional section spacing; no accidental tiny gaps or giant dead zones; card widths from grids; alignment lines repeat.
- **Typography:** hero is the strongest element; ≤4–5 distinct text sizes; body never too wide; tight heading line-height; clear text-color hierarchy; no awkward single-word wraps.
- **Cards:** consistent radius and padding; not over-boxed; subtle borders; restrained shadows.
- **Color:** one accent controls the page; neutral backgrounds dominate; no accidental rainbow; sufficient contrast.
- **Responsive:** 1440px composed not stretched; 1024px not squeezed; 768px reorganizes sensibly; 390px fully usable; 360px zero horizontal overflow.
- **Content:** one primary message; concise copy; believable product visuals; no two sections saying the same thing.
- **Restraint:** removed at least one unnecessary decorative element; removed any component that exists only because "landing pages usually have one"; no gratuitous gradients/badges/animation.

Final self-critique: does it look expensive because every decision appears intentional? Does it look generated? Is there enough whitespace? Would it still look elegant with all shadows removed? Would a designer complain about random spacing values? Does mobile feel designed rather than stacked?

**The governing principle: elegance comes from proportion, hierarchy, restraint, and repetition.** Choose spacing over decoration, typography over effects, alignment over novelty, one excellent visual over six mediocre ones, coherence over variety, calm confidence over visual noise.
