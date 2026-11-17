# Induction → Standardized Prompt Generation (Design Concept)

_June 2, 2026 — Discussed but not yet built._

## The Problem

The prompt builder currently requires manual configuration per tenant (brand voice, sector context, security guardrails, channel prompts). Each new tenant needs a human to write or copy-edit these sections. The published prompt format has been corrupted multiple times by bugs in the assembly code. There's no canonical template for what a "good" prompt looks like.

## The Vision

A standardized prompt-writing framework that:

1. **Defines a canonical format** for every section — Brand → Sector → Security → Channels → Final
2. **Pulls from induction documents** — tenant's knowledge base, uploaded decks, configuration → agent derives the prompt automatically
3. **Is inherited by every tenant** — every new onboarding generates a coherent prompt from their induction data
4. **Never uses an LLM to "compile"** — pure deterministic concatenation from structured sources

## The Architecture

```
Tenant Induction Docs
       │
       ▼
Standardization Engine
  ├── Brand & Personality → from deck tone / company values / agent config
  ├── Sector Intelligence → from competitive landscape / value propositions / case studies
  ├── Security & Guardrails → from compliance docs / restricted claims / escalation policies
  ├── Channel Prompts → from channel config (WhatsApp/Email/Call structure templates)
  └── Final → concatenation of all above (same as current compilePbPrompt / assembleSystemPrompt)
       │
       ▼
Prompt stored as systemPrompt + promptParts in CadenceConfig
       │
       ▼
Inherited by every tenant
```

## What's Needed

1. **A style anchor** — Greg's original Brand & Personality prompt as the canonical template. From this, all other sections derive their format, tone, and structure conventions.

2. **Section templates** — Each section (Brand, Sector, Security, WhatsApp, Email, Call) needs a standard output format. These would be templates in the `prompt_builder_template.py` or a new skill.

3. **Induction → Section mapping** — Which induction document fields map to which prompt sections. For example:
   - Deck "Company Values" → `brandPersonality.personality`
   - Deck "Target Audience" → `sectorSpecific.valueProps`
   - Compliance policies → `security.injectionPrevention`

4. **Tenant inheritance** — Every tenant gets the standard prompts on creation. Can override via the Prompt Builder.

## Next Steps (Per Greg)

1. Greg will share his original Brand & Personality prompt as the style anchor
2. The agent (Johnny) will adapt all other sections to match that style
3. Package as a skill that every tenant profile inherits
