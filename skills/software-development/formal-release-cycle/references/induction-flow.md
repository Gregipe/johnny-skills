# Induction Flow — Complete Tenant Onboarding

## Phases

### Phase 0: Account Creation
Tenant created with bare settings (admin empty, agent=default, industry empty).

### Phase 0.5: Knowledge Base Ingestion
- Upload PDFs/docs → `extract_skills_from_document()` (chunked, anti-hallucination)
- Crawl website → `knowledge_crawler.py` → `extract_skills_from_document()`
- Skills populate DB across categories: proposition, gtm_learnings, inbound, guardrail, segment_signal

### Phase 1-5: Induction Chat (5 modules)

| Module | Category | What Ava asks |
|--------|----------|---------------|
| 0 — Account Setup | `account` | Name, email, WhatsApp, industry, language, personality tone, team structure |
| 1 — Proposition | `proposition` | What, segments, value prop per segment |
| 2 — GTM Learnings | `gtm_learnings` | Channels, objections, what worked/failed |
| 3 — Inbound Setup | `inbound` | Lead sources, CRM, follow-up process |
| 4 — Guardrails | `guardrail` | Pricing, discounts, communication rules |

**Pre-loaded knowledge**: Ava acknowledges skills from Phase 0.5, probes deeper, never re-asks known facts.

**Document context**: Full document text is injected (was truncated to 3000 chars, now unlimited).

### Phase 6: Post-induction
- Induction quality score (0-100)
- Gap identification
- All skills saved to DB

## Key Implementation Details

### Module 0 was added by:
1. Adding `"account": "Account Setup"` to `get_induction_state()` categories
2. Adding Module 0 to `INDUCTION_SYSTEM_PROMPT` before Module 1
3. Adding "Pre-loaded Knowledge" section with acknowledge-then-probe instructions
4. Removing `[:3000]` truncation from document context in induction chat init

### Pre-loaded Knowledge Instructions (in system prompt)
> You must ACKNOWLEDGE what's already known before asking your first question. DO NOT re-ask about facts already in the knowledge base. USE the knowledge base as a foundation, not a blank slate.
