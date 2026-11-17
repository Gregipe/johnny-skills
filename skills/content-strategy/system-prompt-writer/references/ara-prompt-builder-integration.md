# ARA Prompt Builder Integration

How the prompt builder works and how to properly populate it when generating or updating a system prompt.

## Data Flow

```
DB (cadence_configs.config)
  → API (/api/cadence/config)
    → fetchFromServer() updates TEMPLATES (in-memory)
      → saveData() persists to localStorage (ara_cadence_data)
        → applyPbData() populates individual tab fields
          → compilePbPrompt() assembles Final tab display
```

### Key JavaScript Objects

- `TEMPLATES` — In-memory object, keyed by template_id ('cold', 'inbound', 'nurture')
- Each template has: `systemPrompt` (string), `promptParts` (object), `steps`, etc.
- `localStorage key: 'ara_cadence_data'` — persists TEMPLATES between page loads
- `getTemplate()` — returns `TEMPLATES[currentTemplateId]`

### Critical Quirk: localStorage Caching

When you update the DB directly (via Python script or API call), **the page loads from localStorage first, not from the server**. The server data arrives asynchronously via `fetchFromServer()`.

**If the compiled prompt doesn't update after a DB save:**
1. Check if `localStorage.getItem('ara_cadence_data')` has the new data
2. If not, the page loaded from cache. Clear with: `localStorage.removeItem('ara_cadence_data')`
3. Hard refresh (Cmd+Shift+R)

## How compilePbPrompt Works (Current)

The function assembles the Final tab by reading from individual tab textareas in this priority:

1. **DOM textareas first** (`querySelector('#id.pb-textarea')`) — captures real-time edits
2. **promptParts fallback** — for tabs not yet visited (lazy-loaded)
3. **systemPrompt fallback** — only if ALL textareas are empty AND all promptParts paths are empty

### Section Order (canonical)

```
1. Brand Voice                    → pe_phrases (DOM) or promptParts.brandPersonality.phrases
2. Sector Context                 → pe_valueProps (DOM) or promptParts.sectorSpecific.valueProps
3. Security & Guardrails          → pe_injectionPrevention (DOM) or promptParts.security.injectionPrevention
4. WhatsApp                       → pe_whatsappStructure (DOM) or promptParts.channelSpecific.whatsapp.structure
5. Email — Subject Lines          → pe_emailSubject (DOM) or promptParts.channelSpecific.email.subject
6. Email                          → pe_emailBody (DOM) or promptParts.channelSpecific.email.body
7. Call                           → pe_callIntro (DOM) or promptParts.channelSpecific.call.intro
8. Industry Contextualization     → promptParts.sectorSpecific.caseStudies
9. FOMO & Curiosity               → promptParts.sectorSpecific.fomo
10. Message Structure Principles  → promptParts.brandPersonality.personality
11. Sequence Evolution Logic      → promptParts.channelSpecific.email.sequencing
12. Important Communication Rules → promptParts.security.faqs
```

Sections are separated by `\n\n---\n\n`.

## ⚠️ DOM Pitfall: Duplicate IDs

**`cadence_template.py` and `prompt_builder_template.py` define elements with the same `id` attributes.**

For example:
- `cadence_template.py` line 924: `<textarea class="sec-input" id="pe_valueProps">` (sidebar)
- `prompt_builder_template.py` line 193: `<textarea class="pb-textarea" id="pe_valueProps">` (prompt builder)

`document.getElementById('pe_valueProps')` returns the FIRST match (sidebar, empty). This affects `pe_phrases`, `pe_valueProps`, `pe_injectionPrevention`, `pe_whatsappStructure`, `pe_emailBody`, `pe_callIntro`, and `pe_emailSubject`.

**Fix:** Use `document.querySelector('#id.pb-textarea')` to target the prompt builder's version specifically. This applies to:
- `setPbVal()` — now uses `pb.querySelector('#id.pb-textarea') || pb.querySelector('#id')`
- `compilePbPrompt()` — now uses `document.querySelector('#id.pb-textarea')` for all textarea reads

## ⚠️ DOM Pitfall: Lazy-Loaded Tabs

Only the currently visible tab's textareas exist in the DOM. If the user never visits the Email tab, `pe_emailSubject`, `pe_emailBody`, and `pe_emailSequencing` are not in the DOM. `document.querySelector()` returns null.

**Fix:** Always fall back to `promptParts` data when the DOM element is missing. The pattern:

```javascript
var domField = document.querySelector('#pe_emailBody.pb-textarea');
var value = domField ? domField.value.trim() : '';
if (!value && t.promptParts) {
  value = t.promptParts.channelSpecific?.email?.body || '';
}
```

## Email Subject Line Handling

The email subject line is in a **separate textarea** (`pe_emailSubject`) from the email body (`pe_emailBody`). The Final tab inserts it as a dedicated section:

```
## Email — Subject Lines

<subject line content>

---

<email body content>
```

This ensures edits to the subject propagate independently from the body. The `compilePbPrompt()` function handles this by checking `pe_emailSubject` (DOM then promptParts) and prepending it with the "Email — Subject Lines" heading when content exists.

## Segment Field Mapping

| Tab | Field in promptParts | Form element ID | Purpose |
|-----|---------------------|-----------------|---------|
| Brand | `brandPersonality.phrases` | `pe_phrases` | Full brand voice text |
| Brand | `brandPersonality.tone` | `pe_tone_chips` | Tone selector (chip) |
| Brand | `brandPersonality.style` | `pe_style` | Style dropdown |
| Brand | `brandPersonality.vocabulary` | `pe_vocabulary` | Vocabulary dropdown |
| Brand | `brandPersonality.language` | `pe_language_chips` | Language chip |
| Brand | `brandPersonality.personality` | `pe_personality` | Personality description |
| Sector | `sectorSpecific.valueProps` | `pe_valueProps` (⚠️ dup) | Full sector context |
| Sector | `sectorSpecific.caseStudies` | `pe_caseStudies` (⚠️ dup) | Case studies |
| Sector | `sectorSpecific.competition` | `pe_competition` | Competition positioning |
| Sector | `sectorSpecific.customers` | `pe_customers` | Current customers |
| Sector | `sectorSpecific.pricing` | `pe_pricing` | Pricing model |
| Sector | `sectorSpecific.fomo` | `pe_fomo` | FOMO messaging |
| Security | `security.injectionPrevention` | `pe_injectionPrevention` | Full security rules |
| Security | `security.restrictedClaims` | `pe_restrictedClaims` | Restricted claims |
| Security | `security.escalation` | `pe_escalation` | Escalation rules |
| Security | `security.faqs` | `pe_faqs` | FAQ/gotchas |
| WhatsApp | `channelSpecific.whatsapp.structure` | `pe_whatsappStructure` | Full WhatsApp section |
| WhatsApp | `channelSpecific.whatsapp.sequencing` | `pe_whatsappSequencing` | Sequencing rules |
| WhatsApp | `channelSpecific.whatsapp.tone` | `pe_whatsappTone` | Channel-specific tone |
| Email | `channelSpecific.email.subject` | `pe_emailSubject` (⚠️ dup) | Subject line rules |
| Email | `channelSpecific.email.body` | `pe_emailBody` (⚠️ dup) | Full Email section |
| Email | `channelSpecific.email.sequencing` | `pe_emailSequencing` | Sequencing rules |
| Call | `channelSpecific.call.intro` | `pe_callIntro` (⚠️ dup) | Full Call section |
| Call | `channelSpecific.call.discovery` | `pe_callDiscovery` | Discovery questions |
| Call | `channelSpecific.call.objections` | `pe_callObjections` | Objection handling |
| Call | `channelSpecific.call.booking` | `pe_callBooking` | Booking/CTA rules |

Fields marked `(⚠️ dup)` have duplicate IDs in `cadence_template.py` — always query with `.pb-textarea` selector.

## Population Workflow

When generating a system prompt, BOTH must be populated for the prompt builder to work correctly:

1. **`systemPrompt`** — The full compiled text (all sections concatenated with `\n\n---\n\n`)
2. **`promptParts`** — Each section's text placed into the appropriate field

The `generate_system_prompt` function in server.py handles both. After generation, apply the localStorage fix to ensure the FE shows fresh data.

## Files

- `prompt_builder_template.py` — Prompt builder UI (overlay), `compilePbPrompt()`, `applyPbData()`, `collectPbParts()`
- `cadence_template.py` — Main cadence page, `getTemplate()`, `fetchFromServer()`, `saveData()`, `DEFAULT_TEMPLATES`, `setVal()` (⚠️ separate from `prompt_builder_template.py`'s `setPbVal()`)
- `server.py` — API endpoints: `/api/cadence/config`, `/api/cadence/publish`, `/api/cadence/prefill`, `/api/cadence/generate-prompt`
