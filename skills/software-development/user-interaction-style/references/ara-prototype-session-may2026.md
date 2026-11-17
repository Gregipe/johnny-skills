# ARA Prototype Session — May 2026

## Product
Autonomous Revenue Agent (ARA) — a coachable multi-tenant SDR agent.
Sells **Hunar.ai** (voice AI for frontline workforce management).

## Architecture Decisions (from interrogation)

### Multi-Agent Ladder
- **LDR** (Phase 2): Lead enrichment, list building, data cleanup
- **BDR** (Phase 2): Outbound campaigns, A/B testing, multi-channel sequencing, meeting booking. Calling is a skill shared with SDR.
- **SDR** (Phase 1, current build): Inbound lead engagement → qualification → close

Atomic unit: **lead owner** transfers between agents based on outcome.
Shared context: all agents share one email inbox.
Inbound starts at SDR. Outbound starts at LDR → BDR → SDR.

### Induction-First Launch
Customer MUST complete induction before agent goes live.
4 modules: Proposition → GTM Learnings → Inbound Setup → Policy & Guardrails.
Induction score shown to customer. Weakly trained agent flagged.

### Coaching Model
Conversational interface (like Johnny coaches Greg).
Corrections persist per customer as skills.
Agent improves over time. Escape velocity at ~5% error rate.

### Tech Stack (Prototype)
- FastAPI + SQLite + SQLAlchemy
- DeepSeek V4 Flash (SDR conversations)
- DeepSeek V4 Pro (mid-tier coding)
- Claude Sonnet 4 (heavy architecture)
- Multi-tenant via tenant_id column (logical, not Docker)
- Port 8766

### UI
- Single-tenant by default
- Tabbed induction interface (5 tabs: Overview, Proposition, GTM, Inbound, Policies)
- Skill-save toast animations
- Module completion confetti
- Light theme (#f8fafc background)
- Root URL (/) redirects to induction chat

### Channels (Prototype)
- Telegram as WhatsApp proxy
- Email via Himalaya (to be configured)
- Voice: Stubbed, architecture documented

### Key Files
- `/Users/greg/ara/server.py` — FastAPI backend
- `/Users/greg/ara/database.py` — SQLAlchemy models
- `/Users/greg/ara/induction_engine.py` — LLM-driven induction
- `/Users/greg/ara/induction_template.py` — HTML template
- Server runs at http://localhost:8766
