# Prompt Builder — Full-Screen Slide-Over

The cadence system prompt editor (/cadence page) opens a **full-screen slide-over**
from the right when the user clicks "✎ Open Builder". Three-column layout:
sidebar | main workspace | live stats panel.

Template file: `prompt_builder_template.py` (exports `PROMPT_BUILDER_HTML`).
Embedded in `cadence_template.py` via string concatenation:
```python
from prompt_builder_template import PROMPT_BUILDER_HTML
CADENCE_HTML = r"""...""" + PROMPT_BUILDER_HTML + "</body>\n</html>"
```

## Slide-Over Architecture

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ ← Back to Cadence  │  Prompt Builder           Save  Val Pub ✕│  ← Top bar
├─────────────────────┼──────────────────────────────────────────┤
│ Modules             │  1 Brand → 2 Sector → 3 Sec → 4 Wa →    │  ← Arch bar
│   ● Brand & Pers    │  5 Em → 6 Call → F Final                │
│   ● Sector Intel    ├───────────────────────────┬──────────────┤
│   ● Security        │                           │  Live Stats  │
│   Channels          │   Tab content area         │──────────────│
│   ● WhatsApp        │   (scrolls per section)   │  Token Usage │
│   ● Email           │                           │  ████░░░░░░  │
│   ● Call            │                           │──────────────│
├─────────────────────┴───────────────────────────┴──────────────┤
│ G · Admin · Hunar.ai                                           │  ← Footer
└─────────────────────────────────────────────────────────────────┘
```

### Three Columns

| Column | Width | Content |
|--------|-------|---------|
| **Sidebar** | 200px | AR branding, module nav with active dots, "Back to Cadence" link, user avatar |
| **Workspace** | `flex:1` | Top bar, architecture bar, tab content (scrolls) |
| **Live Stats** | Only visible on Final tab | Token counter, context bar, module breakdown, validation |

### Animation

- Slide-over: `transform: translateX(100%) → translateX(0)` with `cubic-bezier(.22,.61,.36,1)` over 300ms
- Backdrop: `background: rgba(0,0,0,.35)` with `backdrop-filter: blur(4px)`
- Click backdrop or ✕ to close. Escape key also closes.

### CSS Class Prefix

All styles use the `pb-` prefix: `.pb-overlay`, `.pb-slideover`, `.pb-sidebar`,
`.pb-workspace`, `.pb-topbar`, `.pb-arch-bar`, `.pb-content`, `.pb-tab-*`.

No conflict with the main cadence page styles.

## Architecture Bar

6 steps in order — arch bar step count: call = numbered `7`, final = badge `F`:

```
1 Brand → 2 Sector → 3 Security → 4 WhatsApp → 5 Email → 7 Call → F Final
```

- Steps with `final` class have `F` number only
- Active step: `background: #E8E8ED`, number circle: `background: #111`, text: `#111`
- Inactive: gray number circle, `color: #9A9A9E`
- Hover: `color: #111`, `background: #F0F0F2`

HTML structure:
```html
<div class="pb-arch-step active" data-tab="brand">
  <span class="pb-arch-num">1</span>
  <span class="pb-arch-label">Brand</span>
  <span class="pb-arch-check">✓</span>
</div>
<div class="pb-arch-connector"></div>
...
<div class="pb-arch-step final highlight" data-tab="final">
  <span class="pb-arch-num">F</span>
  <span class="pb-arch-label">Final</span>
</div>
```

Clicking an arch step calls `switchPbTab(tabId)`.

**IMPORTANT:** Behavioral routing for arch steps uses `data-tab` attribute, not CSS class. The `final` CSS class is for styling only (compact badge). Never use `classList.contains('final')` for event routing — use `dataset.tab !== 'final'` instead. See `ara-frontend-patterns` pitfall #15.

## Tab Contents

### 1. Brand & Personality
| Input | Type | ID |
|-------|------|----|
| Tone | 9 radio chips | `pe_tone_chips` (values: sophisticated, consultative, calm, confident, warm, formal, friendly, persuasive, analytical) |
| Style | Select | `pe_style` (direct, consultative, storytelling, provocative) |
| Vocabulary | Select | `pe_vocabulary` (executive, startup, technical, simplified, strategic) |
| Language | 5 radio chips | `pe_language_chips` (auto, english, hinglish, hindi, regional) |
| Phrases | Textarea | `pe_phrases` |
| Live Greeting Preview | Display card | `pe_voicePreview` |

### 2. Sector Intelligence
Grid of 8 expandable modular cards. Clicking a card opens a detail textarea below.
Cards: Value Proposition (expanded by default), Case Studies, Competitor References,
Existing Customers, Pricing References, FOMO Triggers, Industry Pain Points, Sector Decks.

| Input | Type | ID |
|-------|------|----|
| Value Proposition | Textarea | `pe_valueProps` |
| Detail area (shows on card click) | Textarea | `pe_sectorDetailText` |

### 3. Security & Guardrails
Policy blocks with headers and textareas:

| Input | Type | ID |
|-------|------|----|
| Prompt Injection Prevention | Textarea | `pe_injectionPrevention` |
| Restricted Claims | Textarea | `pe_restrictedClaims` |
| Escalation Rules | Textarea | `pe_escalation` |
| FAQs & Approved Answers | Textarea | `pe_faqs` |

**Working hours and compliance settings have been removed from the prompt builder.** They belong at the cadence template level in the Reachout Conditions section (`condWorkingHours`, `condWeekdays`, `condSaturday`, `condSunday`) on the main cadence page.

### 4. WhatsApp (previously Tab 4)
| Input | Type | ID |
|-------|------|----|
| Message Structure | Textarea (tall) | `pe_whatsappStructure` |
| Sequence Behavior | Textarea | `pe_whatsappSequencing` |
| Tone Adaptation | Textarea | `pe_whatsappTone` |
| Example Message (right) | Display | `pe_whatsappExample` |

### 5. Email (previously Tab 5)
| Input | Type | ID |
|-------|------|----|
| Subject Line Strategy | Textarea | `pe_emailSubject` |
| Body Structure | Textarea (tall) | `pe_emailBody` |
| Sequence Strategy | Textarea | `pe_emailSequencing` |
| Subject Line Preview (right) | Display | `pe_emailSubjectPreview` |

### 6. Voice Call (previously Tab 6)
| Input | Type | ID |
|-------|------|----|
| Introduction Style | Textarea | `pe_callIntro` |
| Discovery Flow | Textarea (tall) | `pe_callDiscovery` |
| Objection Handling | Textarea | `pe_callObjections` |
| Meeting Booking | Textarea | `pe_callBooking` |
| Call Objective Builder (right) | Display | `pe_callObjective` |

### Final Tab — System Prompt

Right side (live stats):
| Element | Description | ID |
|---------|-------------|----|
| Section chips | [Full] [Brand] [Sector] [Security] [Channels] | `.pb-section-chip` |
| Prompt display | Code-editor container | `pbFinalPrompt` |
| Contradictions | Warning/OK display | `pbContradictions` |
| Copy button | Clipboard copy | — |
| Export button | Downloads .txt | — |
| Validate & Compile | LLM call | `pbValidateBtn` |

Right side (live stats):
| Card | Content | ID |
|------|---------|----|
| Token Usage | Total tokens + context bar + % | `pbTotalTokens`, `pbContextBar`, `pbContextPct` |
| Module Breakdown | Per-section token counts | `pbModuleList` |
| Validation | Contradictions, variables, channels | `pbDotContradictions`, `pbContradictionsCount`, `pbVariableCount`, `pbChannelCount` |

## Data Model (promptParts)

```javascript
{
  objective:            "Book qualified discovery conversations...",
  brandPersonality: {
    tone:               "calm|confident|warm|formal|funny|persuasive|...",
    style:              "direct|consultative|storytelling|provocative",
    vocabulary:         "startup|executive|technical|simplified|strategic",
    language:           "auto|english|hinglish|hindi|regional",
    phrases:            "Hunar.ai-specific vocabulary. Avoid:..."
  },
  sectorSpecific: {
    valueProps:         "...",
    caseStudies:        "...",
    competition:        "...",
    customers:          "...",
    pricing:            "...",
    fomo:               "...",
    deckRef:            ""
  },
  security: {
    injectionPrevention:"...",
    restrictedClaims:   "...",
    escalation:         "...",
    faqs:               "..."
  },
  channelSpecific: {
    whatsapp: {
      structure:        "...",
      sequencing:       "...",
      tone:             "..."
    },
    email: {
      subject:          "...",
      body:             "...",
      sequencing:       "..."
    },
    call: {
      intro:            "...",
      discovery:        "...",
      objections:       "...",
      booking:          "..."
    }
  }
}
```

Note: `workingHours` and `weekdays` were removed from `security` in the prompt builder data model (May 2026). These settings now live at the cadence template level under `t.conditions` in the cadence steps selector. The runtime (`server.py`) reads `conditions` from the template config, not from promptParts — this was already the case before the removal.

### Sidebar Footer — Prompt Builder vs Dashboard

The Prompt Builder's sidebar footer differs from the main ARA dashboard sidebar — the user explicitly removed the role text. The prompt builder shows only `avatar + name`, while the dashboard sidebar shows `avatar + name + role`.

## Button Persistence (Backend-First)

Save Changes and Publish now POST to the backend, not just localStorage:

### Save Changes
Uploads to `/api/cadence/save-draft` with `template_id`, `promptParts`, and `systemPrompt`, then falls back to `saveCurrentState()` for localStorage.

### Publish
Uploads to `/api/cadence/publish` with the full template + promptParts + compiled prompt. On success, closes the builder and reloads templates via `loadTemplates()`.

### Design Principle
Every button must verifiably modify the prompt in the database — never use localStorage-only persistence for Save or Publish buttons.

## Prefill Generator Architecture (Path B — Deterministic Templates)

The prefill endpoint at `GET /api/cadence/prefill` returns **structured JSON that matches the form field shapes** — no LLM calls, no JSON parse risk, instant response (<100ms).

### Architecture

Skills table (`skills`) → prefill templates (`prefill_generator.py`) → structured JSON → form fields.

**Three sources feed the skills table:**
1. **Induction docs** — uploaded by Greg (pain points, competition, pricing, restricted claims, etc.)
2. **Conversation learnings** — daily 6AM IST cron extracts patterns from 24h of conversations (objections, messaging wins, engagement patterns)
3. **Coaching capture** — instant skill save when Greg tells Ava "next time do X" in chat

All three land in the same `skills` table with category/key/value structure. Prefill reads from here at open time.

### Key Design Decision

**Path B (deterministic templates) over Path A (LLM generation):**
- ✅ Instant (<100ms) — no user waits
- ✅ Deterministic — always consistent, no JSON parse failures
- ✅ Always available — no LLM dependency or API timeout risk
- ✅ Rich content — 10K+ chars of GTM-operator quality per cadence
- ⚠️ Fixed content — updated via induction/skills, not on every open

### Response Shape (MUST match form field IDs)

```json
{
  "status": "ok",
  "prefill": {
    "cold": {
      "objective": "...",
      "brandPersonality": {
        "tone": "persuasive|warm|formal|friendly|consultative",
        "style": "direct|consultative|storytelling|provocative",
        "vocabulary": "executive|startup|technical|simplified|strategic",
        "language": "auto|english|hinglish|hindi|regional",
        "phrases": "..."
      },
      "sectorSpecific": {
        "valueProps": "...",
        "caseStudies": "...",
        "competition": "...",
        "customers": "...",
        "pricing": "...",
        "fomo": "...",
        "deckRef": ""
      },
      "security": {                              // OBJECT, not string
        "injectionPrevention": "...",
        "restrictedClaims": "...",
        "escalation": "...",
        "faqs": "..."
      },
      "channelSpecific": {
        "whatsapp": {                            // OBJECT, not string
          "structure": "Intro → Hook → Context → CTA → Signature",
          "sequencing": "...",
          "tone": "Warm, direct..."
        },
        "email": {                               // OBJECT, not string
          "subject": "Personalize with {{first_name}}...",
          "body": "...",
          "sequencing": "..."
        },
        "call": {                                // OBJECT, not string
          "intro": "Context → State purpose → Ask permission",
          "discovery": "...",
          "objections": "...",
          "booking": "..."
        }
      }
    }
  }
}
```

### Tone Mapping

When prefill reads existing `brandVoice.tone` from the config, it maps to the Prompt Builder's chip values:
- `funny` → `persuasive`
- `warm` → `warm`
- `formal` → `formal`
- `casual` → `friendly`
- Default → `consultative`

### Prefill Loading Flow

1. **Page loads** → `renderCurrentTemplate()` calls `prefillFromInduction()`
2. Checks `t.promptParts` — if already populated, skip
3. Fetches `GET /api/cadence/prefill?template_id=<current template id>`
4. Stores response in `t.promptParts` + renders chips via `renderPromptOverview()`
5. Prompt Builder's `loadPromptBuilderData()` also checks and fetches if empty

**CRITICAL:** The frontend fetch must include `?template_id=` to get only the relevant cadence. Without it, the backend returns all three and the frontend loses the targeted response.

### Cadence-Specific Personae

| Cadence | Persona | Default Actions | Default Tone |
|---------|---------|-----------------|--------------|
| Cold | Witty, consultative, persuasive | WhatsApp(D0) → Email(D4h) → Call(D48h) | persuasive |
| Inbound | Direct, qualifying, fast-moving | Email(D0) → Call(D24h) → WhatsApp(D48h) | warm |
| Nurture | Patient, educational, strategic | Email(D0) → WhatsApp(D72h) → WhatsApp(D144h) | friendly |

### Security Content (Notably Production-Tested)

The security section includes a real DeepSeek-specific guardrail:
> "DeepSeek has a known issue of switching languages based on lead names or city cues. You ALWAYS respond in English..."

This lives in the skills table under `prohibited_promises` category and is read by the prefill templates.

### Implementation Files

- `prefill_generator.py` — `generate_prefill(tid, existing_config)` builds the full structured response
- `server.py` — `GET /api/cadence/prefill` endpoint calls `generate_prefill()`
- `cadence_template.py` — `prefillFromInduction()` frontend fetch + `renderPromptOverview()` chips
- `extract_conversation_learnings.py` — daily 6AM IST cron for conversation patterns
- `coaching_capture.py` — instant coaching detection on chat

### Prefill Data Model (Legacy — Do Not Use)

The OLD prefill returned flat strings for security/channel sections. This caused all form fields to be empty in the Prompt Builder. The fix was converting to the structured object shape above. **Never return strings for fields the form expects as objects.**

## JS Functions

All live in the `<script>` tag at the bottom of `PROMPT_BUILDER_HTML`:

| Function | Action |
|----------|--------|
| `openPromptBuilder()` | Opens slide-over, calls `loadPromptBuilderData()`, registers Escape key handler, sets `body.style.overflow = 'hidden'` |
| `closePromptBuilder()` | Closes slide-over, restores body scroll, removes key handler |
| `switchPbTab(tabId)` | Switches active tab + sidebar item + arch step |
| `loadPromptBuilderData()` | Reads `t.promptParts` or `promptPartsCache`. If both empty, calls prefill API with `?template_id=t.id`. Otherwise calls `applyPbData()` |
| `applyPbData(pp, cache)` | Populates all pe_* fields from promptParts data |
| `collectPbParts()` | Reads all pe_* fields into a promptParts object |
| `validateAndCompilePrompt()` | POSTs to `/api/cadence/validate`, populates Final tab + live stats |
| `updateLiveStats(data)` | Updates token counter, context bar, module breakdown, validation from validate response |
| `savePromptBuilder()` | Saves to BACKEND via POST `/api/cadence/save-draft` + localStorage fallback. Shows "✓ Saved to draft" toast. |
| `publishPromptBuilder()` | Saves to BACKEND via POST `/api/cadence/publish`, closes, reloads templates. |
| `copyPrompt()` | Clipboard write |
| `exportPrompt()` | Downloads as .txt |
| `fetchPrefill()` | GETs `/api/cadence/prefill?template_id=t.id`, stores in `t.promptParts` + `promptPartsCache`, calls `applyPbData()` |

## Pitfalls

1. **`setVal` needs a closing brace.** The `setVal` function has two closing braces:
   one for the `if (el)` block, one for the function. Missing the second brace
   silently breaks the ENTIRE script (all functions become undefined).

2. **`JSON.parse pitfall with LLM output.** The prefill generator calls DeepSeek V4 Flash to generate rich section content. `call_llm()` defaults to `max_tokens=2048` which is insufficient for the 7+ section JSON response. Bump to 32768 for any LLM call generating large structured output. JSON parsing should use three fallback strategies: `json.loads(strict=False)`, `decoder.raw_decode()`, and brace-tracking with string-literal awareness.

3. **Slide-over has NO scroll on body.** When the slide-over is open,
   `body.style.overflow = 'hidden'` prevents background scrolling. Restored on close.

4. **Sector detail textarea.** Clicking a sector module card opens a shared detail
   textarea below the grid (`pe_sectorDetailText`). It replaces the placeholder
   text, not a specific field. Only one detail area is visible at a time.

5. **validate endpoint can timeout.** LLM calls may take 15-30s. The UI shows
   "⏳ Validating..." on the button during the call.

6. **Removing a tab from the prompt builder requires auditing ALL these surfaces:**
   - Sidebar nav item (`.pb-nav-item[data-pb-tab="..."]`)
   - Architecture bar step (`.pb-arch-step[data-tab="..."]`)
   - Tab panel HTML (`<div class="pb-tab" id="pbTab-...">`)
   - Section chip in Final tab toolbar (`.pb-section-chip[data-section="..."]`)
   - CSS styles for the tab's components (`.pb-tl-*`, etc.)
   - JS event handler conditions if the tab used CSS class-based exclusion
   - Sidebar nav section heading (if the nav section is now empty, remove it)
   - Prefill/load/save logic (`collectPbParts`, `applyPbData`)
   - The sidebar "Orchestration" section (if Sequencing was the only item)
   
   **Don't forget** to check `shared-ui-propagation` — the sidebar is duplicated
   across template files and the dashboard.

7. **The "Orchestration" sidebar section should NOT be empty.** If the Sequencing
   Strategy nav item is removed and it was the only item under "Orchestration",
   remove both the nav section divider and the empty section.

8. **`file` tool order — patching HTML is safer than file.** When removing large
   HTML blocks, prefer `patch` over `sed` in terminal to avoid backslash-escaping
   issues with the raw string template format.
