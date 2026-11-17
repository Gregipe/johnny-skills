# Standardized Prompt Generation from Induction — BUILT

**Status:** ✅ BUILT. Session June 2, 2026.

**Endpoint:** `POST /api/cadence/generate-prompt` in `server.py`

**Section templates:** `prompt_templates.json` in the project root (loaded at server startup)

## What Was Built

A backend endpoint that auto-generates complete system prompts for any tenant from induction documents. Ava triggers this after induction completes. No manual prompt writing required.

## Architecture

### Inheritance Model

| Layer | Inherited? | Source |
|-------|-----------|--------|
| **Brand & Personality** | ✅ Fully inherited | `prompt_templates.json` — verbatim across all tenants |
| **Security & Guardrails** | ✅ Fully inherited | `prompt_templates.json` — verbatim, tags may vary |
| **Channel Anatomy** (WhatsApp/Email/Call) | ✅ Mostly inherited | `prompt_templates.json` — structure, don'ts same for all |
| **Sector Context** | ❌ Per-tenant | Built from induction docs (capabilities, case studies, positioning) |
| **Industry Contextualization** | ❌ Per-tenant | From configured segments in tenant config |
| **Channel Sequence Rules** | ⚠️ Partially adjusted | Behavioral stages inherited; examples per-tenant |

### Section Templates: `prompt_templates.json`

A JSON file in the project root that stores all canonical section text. Loaded at server startup, avoiding Python triple-quote issues with nested `"` characters in content.

10 sections stored: `Brand Voice`, `Security & Guardrails`, `Lead Context Awareness`, `FOMO & Curiosity`, `Message Structure Principles`, `Sequence Evolution Logic`, `Important Communication Rules`, `WhatsApp`, `Email`, `Call`

### Generation Flow

```
POST /api/cadence/generate-prompt
  │
  ├─ 1. Fetch tenant from DB (name, config, segments)
  ├─ 2. Fetch induction docs (Document table, content_type in deck/pdf/document/text)
  ├─ 3. Extract capabilities, case studies, customer names from doc text
  ├─ 4. Build 13 sections in canonical order:
  │      Objective (tenant name + industry)
  │      Brand Voice (from JSON template — inherited)
  │      Sector Context (from docs — per-tenant)
  │      Security & Guardrails (from JSON — inherited)
  │      WhatsApp (from JSON — inherited, {{tenant_name}} replaced)
  │      Email (from JSON — inherited)
  │      Call (from JSON — inherited)
  │      Lead Context Awareness (from JSON — inherited)
  │      Industry Segments (from tenant config — per-tenant)
  │      FOMO & Curiosity (from JSON — inherited)
  │      Message Structure (from JSON — inherited)
  │      Sequence Evolution (from JSON — inherited)
  │      Communication Rules (from JSON — inherited)
  │
  ├─ 5. Save systemPrompt + promptParts to all 3 templates
  ├─ 6. Return { status, sections, prompt_length, updated }
  └─ 7. User hard refreshes (clears localStorage cache)
```

### Key Design Decisions

**1. JSON file for templates** — Avoids Python triple-quote string issues. Templates contain `"` characters (e.g., `"this person understands our world unusually well."`) which broke `"""..."""` strings. JSON handles this naturally.

**2. Per-template saves only** — The endpoint only updates the compiled prompt (`systemPrompt`) and the flag (`_standard_generated`). It does NOT overwrite existing `promptParts` to preserve any manual edits users may have done to individual fields.

**3. No time delays in sequence rules** — Sequence evolution uses behavioral stages (Opening → Building → Sharpening → Closing). Time delays like `T+3-5d` are NOT embedded — they belong in the cadence step selector, not the LLM prompt.

**4. localStorage cache must be cleared** — After DB write, the FE continues serving cached data from `localStorage['ara_cadence_data']` until cleared. Users MUST hard refresh (`Cmd+Shift+R`) to see the new prompt. The return payload includes a warning about this.

**5. Induction depth determines prompt quality** — If docs have no case studies, capabilities, or specific operational context, the generated sector section is thin. The system-prompt-writer skill now has a mandatory process rule: shallow induction = ask for more, don't proceed with defaults.

### Depth Requirements

Each section must be filled with substantive content, not one-liners:

- **Case Studies**: 3-4 specific deployments with metrics where available
- **Competition**: Market context about alternatives and differentiation
- **Restricted Claims**: Explicit boundaries on what Ava cannot claim
- **Escalation Rules**: 5-6 scenarios with exact phrasing
- **FAQs**: 6-8 Q&A pairs with specific answers
- **Sequence Stages**: Each behavioral stage gets purpose, content structure, and tone description
- **Objections**: 5+ common objections with validation-first handling

## How Ava Triggers It

From the frontend, after induction completes:

```javascript
const res = await fetch('/api/cadence/generate-prompt', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ tenant_id: '...' }),
});
const data = await res.json();
// data.status === 'ok', data.prompt_length === N
// Notify user: "Your system prompt is ready. Hard refresh to see it."
```

## Future Improvements

- Extract capabilities more intelligently from induction docs (currently falls back to defaults)
- Parse case studies with better structure (metrics, industry, outcome)
- Per-tenant segment-specific templates per industry type (Staffing, Logistics, BFSI, etc.)
- Auto-induction: Ava asks the right questions during induction to fill gaps
