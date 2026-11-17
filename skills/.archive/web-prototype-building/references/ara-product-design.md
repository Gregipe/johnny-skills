# ARA — Autonomous Revenue Agent (Product Design)

## Core Concept
A coachable AI SDR agent. Each customer inducts their agent through conversation — teaches it their product, segments, GTM learnings, and guardrails. The agent then engages inbound leads across email/WhatsApp/voice, qualifies them, and drives toward close. The customer corrects the agent through coaching, and the agent improves over time (persistent skills).

## Architecture

### Multi-Agent Roadmap

| Phase | Agent | Job |
|-------|-------|-----|
| V1 | SDR (ARA) | Inbound lead engagement → qualification → close |
| V2 | LDR | Lead enrichment, list building, data cleanup |
| V2 | BDR | Outbound campaigns, A/B testing, multi-channel sequencing, meeting booking |
| Future | Vertical specialization | Insurance, real estate, healthcare |

All agents share a common communication stack (WhatsApp, Email, Voice). Lead ownership transfers between agents. Inbound leads start with SDR.

### Tenant Isolation
- Each customer gets a logically isolated container (tenant_id scoping on all tables)
- Phase 2: Docker container per tenant for true isolation
- Customer brings their own API keys (WhatsApp Business, Twilio/Hunar, CRM)
- Legal liability rests with customer — platform is neutral pipeline

### Communication Stack
- **Email**: Via Himalaya/IMAP (owned by customer's domain)
- **WhatsApp**: WhatsApp Business API (customer's WABA account)
- **Voice**: Hunar Voice AI (sub-500ms latency, Hinglish/Tanglish support, dynamic LLM scripts)
- **Telegram**: Proxy channel for prototype/demo

## Induction Module (Required Before Going Live)

| Section | What's Captured |
|---------|----------------|
| **Proposition** | Use cases, segment-specific value props, competitive advantages |
| **GTM Learnings** | Past wins/losses, sectors that worked/didn't, best channels per segment |
| **Inbound Setup** | Lead sources (Meta, Google, landing pages), CRM connection |
| **Policy & Guardrails** | Pricing limits, discount authority, feature promises, prohibited behaviors, comms windows |
| **Uploads** | PDF playbooks, price sheets, past deal data, term definitions |

The induction is **conversational** — the agent asks questions, and each answer that contains a specific fact is saved as a skill. The customer gets a completion score. Agent won't perform at full capability until sufficiently trained.

### Induction Engine Design (Prototype)
- LLM system prompt with explicit `===SAVE_SKILL==={key, value, category}===END_SAVE_SKILL===` extraction format
- Regex-based skill extraction from LLM response
- Module coverage determined by persisted DB skills (not LLM self-report)
- Induction scoring: 0-100 based on module coverage
- In-memory conversation history (`INDUCTION_SESSIONS` dict)

## Coaching & Evolution

### Persistent Skills
- Every coaching correction is saved as a skill in the DB (per tenant)
- Skills are categorized: proposition, gtm_learning, inbound, guardrail
- Skills persist across sessions — the agent reads them on startup

### Confidence Scoring
- Formula: `confidence = 100 - (human_dependence_count / max(1, total_leads)) * 100`
- As the agent handles more leads independently, confidence rises
- Escalations (human_dependence) decrease confidence

### Escape Velocity
- When human dependence drops below ~5% of all situations, agent can propose expanded autonomy
- Agent has a "performance review" with the customer (weekly check-in)
- Guardrails can be relaxed over time, like a human employee
- Conversation modeled on human performance appraisals (NDR reviews)

### Weekly Check-in
- Structured performance review conversation
- Agent presents metrics (leads handled, conversion rate, escalations)
- Agent reflects on patterns observed
- Customer provides structured feedback
- Goal alignment for next period
- Agent proposes skill improvements (with customer permission/research)

## Core Differentiator vs Competitors
Unlike Apollo, 11x.ai, Gong, etc.:
- **Conversational induction** — no config forms, no dashboards. The customer TEACHES the agent through conversation
- **Coachable** — the agent learns from corrections like a human employee, not from retraining
- **Earns autonomy** — starts supervised, gains independence through demonstrated competence
- **Multi-tenant by nature** — each customer's agent is their own, no shared brain

## Hunar.ai Integration
ARA is built on Hunar.ai's voice infrastructure:
- Dynamic LLM-generated call scripts with variables ({callee_name}, {product_name})
- Output: disposition, transcript, recording
- Sub-500ms latency, multi-language (Hinglish, Tanglish)
- Interruption handling
- 50K+ calls/day capacity

## V1 Prototype Scope (`/Users/greg/ara/`)
- **Backend**: FastAPI + SQLite + SQLAlchemy on port 8766
- **Frontend**: Plain HTML + Tailwind CDN + vanilla JS
- **Induction**: 4-module conversational onboarding with tabbed UI
- **Leads**: Simple form → API → SDR engagement (stubbed)
- **Dashboard**: Metrics, knowledge base, recent leads
- **Tenant**: Single-tenant for prototype (Hunar.ai, ID: 3e736242)

## Files
- `/Users/greg/ara/server.py` — FastAPI app with all endpoints
- `/Users/greg/ara/database.py` — Multi-tenant SQLite schema
- `/Users/greg/ara/induction_engine.py` — LLM-driven induction conversation
- `/Users/greg/ara/induction_template.py` — Induction chat UI (tabs, toasts, animations)
- `/Users/greg/ara/venv/` — Python virtual environment (FastAPI, uvicorn, sqlalchemy, httpx)
