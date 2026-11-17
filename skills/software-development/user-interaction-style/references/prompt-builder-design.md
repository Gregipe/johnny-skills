# Prompt Builder — Design System Reference

## Overview

The Prompt Builder is a full-screen slide-over interface for editing autonomous revenue agent prompts. Built May 2026. Serves as the canonical reference for production SaaS interfaces following the monochrome Apple/Linear/Notion aesthetic.

## Slide-Over Container

- Opens from right edge, 92vw wide (capped at 1440px)
- Backdrop: `backdrop-filter: blur(4px)` over the underlying page
- Animation: `cubic-bezier(0.16, 1, 0.3, 1)` for slide and fade
- Inner: 3-column layout (sidebar | workspace | live stats)

## Three-Column Layout

### Left Sidebar (200px fixed)
- Top: AVATAR logo (24px) + "Autonomous" wordmark
- Module nav: each section as a row with name + activity dot (filled=has content, outlined=empty)
- Active state: subtle gray highlight
- Bottom: user avatar + name
- No nested navigation, no collapsible groups

### Center Workspace (flex)
- **Top bar**: "Prompt Builder" title (24px, bold, #111111) + metadata row (last updated, agent version, languages, channels in small #6E6E73 text)
- **Toolbar**: Save Changes, Validate & Compile, Publish buttons — rounded, monochrome, minimal
- **Architecture bar**: horizontal step flow below top bar. Each step is a rounded pill with number + label + completion dot. Active step has black bg, rest are light gray (`#F5F5F7` bg, `#6E6E73` text)
- **Tab content**: full-height remaining space, scrolls per-section if content overflows

### Right Live Stats Panel (280px fixed)
- Only visible on the Final System Prompt tab
- Token counter with progress bar (context window utilization)
- Module breakdown: each section in a list with token count
- Validation status: contradiction warnings, channel consistency checks
- Sticky positioning — doesn't scroll with tab content

## Architecture Bar

- 8 steps: `1 Objective → 2 Brand → 3 Sector → 4 Security → 5 WhatsApp 6 Email 7 Call → S Sequence → F Final`
- Clickable — clicking a step changes the active tab
- Active step: `#111111` bg, white text
- Inactive steps: `#F5F5F7` bg, `#6E6E73` text
- Arrows between steps: thin `→` in `#E5E5E7`
- Completion indicator: filled dot (has content) vs outlined dot (empty)
- Multi-channel steps (5, 6, 7): three channel icons shown side by side instead of one large step

## Tab Sections

### Objective Tab
- Large heading + subtext
- Textarea with soft rounded corners, placeholder text
- 5 success metric chips (selectable, rounded pills)
- 4 priority sliders (Aggressiveness, Persistence, Formality, Speed vs Precision)
- Sliders: thin track, no numeric labels, semantic endpoints only

### Brand & Personality Tab
- 9 tone chips in a horizontal wrap: Sophisticated, Consultative, Calm, Confident, Warm, Formal, Friendly, Persuasive, Analytical
- Single-select (choose one)
- Style selector (dropdown), Vocabulary selector, Language adaptation selector
- Formality slider (1-5)
- Phrases textarea for guardrails/nonos
- Live greeting preview card: shows how Ava would greet a lead with current settings

### Sector Intelligence Tab
- 8 expandable section cards in a 2-column grid
- Each card has a title + expand arrow + summary preview
- Cards: Value Prop, Case Studies, Competition, Customers, Pricing, FOMO, Pain Points, Sector Decks
- Expanded cards show full textarea content with character count

### Security & Guardrails Tab
- Policy blocks for each rule category
- Each block: warning icon + section title + rule text
- Sections: Injection Prevention, Restricted Claims, Compliance, Working Hours, Escalation Boundaries, Restricted Vocabulary
- Textareas with policy example text as placeholder

### WhatsApp / Email / Voice Call Tabs
- Structured sub-sections with labeled textareas
- WhatsApp: Intro → Hook → Context → CTA → Signature + Sequence behavior descriptions
- Email: Subject line strategy, body structure, sequence strategy
- Call: Intro, Discovery, Objection handling, Meeting booking
- Pre-filled with real conversation-sourced objection handling from skills table

### Sequencing Strategy Tab
- Horizontal timeline with channel nodes
- Each node: channel icon + delay + repeat count + interval
- Add step button at end of timeline
- Delete button on each step

### Final System Prompt Tab
- Section chips at top: colored pills showing which modules contributed to the compiled prompt
- Code-editor container: monospace font, dark bg (`#F5F5F7`), syntax-like formatting
- Right panel shows live stats
- Copy / Export / Validate buttons

## HTML Structure Pattern

```
#pbOverlay (full-screen fixed, z-index: 9999)
  .pb-backdrop (blur)
  .pb-container (3-column flex row)
    .pb-sidebar (200px, flex column)
      .pb-sidebar-header
      .pb-sidebar-nav
      .pb-sidebar-footer
    .pb-workspace (flex column)
      .pb-topbar
      .pb-arch-bar
      .pb-tab-content
    .pb-live-stats (280px, only on Final tab)
```

## CSS Variables

```css
--pb-bg: #FFFFFF;
--pb-panel: #F5F5F7;
--pb-border: #E5E5E7;
--pb-muted: #6E6E73;
--pb-text: #111111;
--pb-radius-sm: 6px;
--pb-radius-md: 10px;
--pb-radius-lg: 14px;
--pb-shadow: 0 2px 8px rgba(0,0,0,0.04), 0 8px 32px rgba(0,0,0,0.08);
--pb-font: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", system-ui;
```

## Key Interactions

- Clicking architecture bar step switches tab
- Save Changes → POST /api/cadence/save-draft (persists to DB)
- Validate & Compile → POST /api/cadence/validate (calls LLM, returns compiled prompt + diagnostics)
- Publish → POST /api/cadence/publish (saves + closes + reloads cadence page)
- Tab content is preserved when switching tabs (not re-rendered)
- Prefill loads from GET /api/cadence/prefill when promptParts are empty
