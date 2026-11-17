# ARA — Autonomous Revenue Agent: Product Vision (May 2026)

Session date: May 19-20, 2026.
Status: **Working prototype** — FastAPI server + induction chat + dashboard running on localhost:8766.

## One-Line Thesis

A coachable, multi-tenant autonomous SDR agent for SaaS companies — inducted through conversation, corrected through coaching, earning autonomy through demonstrated competence.

## Architecture (from interrogation)

### Multi-Tenant Isolation
Each customer gets independent skills/knowledge base (SQLite, tenant_id-scoped), separate guardrails, own channel API keys (WhatsApp Business, email SMTP, voice). Central LLM shared (DeepSeek/Claude), customer identity per-tenant.

### Induction Module (Required Before Go-Live)
Four modules: Proposition (segment-specific value props), GTM Learnings (past wins/losses, channels per segment), Inbound Setup (lead sources, CRM), Policy & Guardrails (pricing limits, discount authority, feature no-promise list, TRAI windows, escalation thresholds). Completion scored — half-trained agent underperforms.

Inputs: conversational answers (via web chat interface), uploaded PDF playbooks, pricing sheets, past deal CSVs. Agent asks clarifying questions after ingestion.

**Current prototype state:** Induction chat works at `/induction/chat/{tenant_id}` with a DeepSeek-powered conversational agent driving the 4-module flow. Skills are saved via `[SAVE_SKILL]` blocks parsed from the LLM response and persisted to the skills table.

### Multi-Agent Handoff (V2, but architected)
- LDR: enrichment, list building
- BDR: outbound campaigns, A/B testing, multi-channel sequencing (voice/WA/email), meeting booking
- SDR (V1 — what's built): inbound engagement → qualification → close
Shared lead record with ownership field — full context follows the lead.

### Coaching Loop (The Moat)
Customer corrects conversationally → agent persists as category/key/value skill → next lead gets updated treatment. Skills are tenant-isolated, editable, and structured (proposition, gtm_learning, guardrail, segment, workflow).

### Confidence Score → Escape Velocity
`100 - (human_dependence / total_leads * 100)`. When <5% dependence, agent can propose expanded autonomy — like an employee in a performance review.

### Escalation
Agent hits guardrail → "Let me check with team" → notify human with full context card → receive decision → resume on appropriate channel.

### Liability
Customer takes full accountability during induction. Agent enforces hard TRAI/DPDP rules. Customer owns legal permission to contact leads.

## Prototype Stack

| Layer | Technology | Status |
|-------|-----------|--------|
| Backend | FastAPI + UVicorn | ✅ Running on :8766 |
| Database | SQLite + SQLAlchemy ORM | ✅ Multi-tenant (tenant_id scoped) |
| Induction Engine | DeepSeek V4 Flash via API | ✅ Running, scored, tabbed UI complete |
| Dashboard | Tailwind HTML + Jinja2 | ✅ /, /leads, /induction |
| SDR Conversation | Hermes (Johnny) | 🔜 Phase 2 |
| Voice | Hunar.ai API | 🔜 Not yet integrated |
| Email | Himalaya CLI | 🔜 Not yet integrated |

### Database Schema
- **tenants**: id, name, induction_score, confidence_score, total_lead_count, error_count, human_dependence_count, config (JSON)
- **skills**: id, tenant_id, category (proposition|gtm_learning|inbound|guardrail|workflow), key, value, created_at, updated_at
- **leads**: id, tenant_id, name, email, phone, company, lead_source, stage (new|contacted|qualified|meeting_booked|closed_won|closed_lost|dormant), assigned_agent, notes
- **conversations**: id, lead_id, tenant_id, channel (email|whatsapp|voice|telegram), direction, content, summary, sentiment
- **coaching_logs**: id, tenant_id, feedback_type (correction|approval|suggestion), context, feedback, skill_updated

### Induction Engine
- System prompt drives structured Q&A across 4 modules
- Skills saved via `===SAVE_SKILL===\n{"category":"proposition","key":"logistics","value":"..."}\n===END_SAVE_SKILL===` blocks in LLM responses (switched from `[SAVE_SKILL]...[/SAVE_SKILL]` after the old format was unreliable — LLM ignored it 100% of the time)
- Progress tracked: module requires ≥2 saved skills to be "covered"; induction_score = covered/total × 100
- Induction auto-completes after all 4 modules covered
- **Scoring correction (May 20):** Initial induction gave 90/100 with 0 skills saved — LLM talked but never persisted. Fixed with: (a) `===SAVE_SKILL===` format front-and-center in system prompt, (b) module coverage requires concrete saved skills, not just LLM saying "done", (c) strict scoring rubric: 0-30 (useless) to 86-100 (comprehensive)
- **UI (Greg's feedback):** Induction page redesigned with tabbed interface (5 tabs: Overview, Proposition, GTM Learnings, Inbound Setup, Policy & Guardrails), skill-save toast animations (bottom-right, 3s fade), module completion confetti + celebrations, knowledge base summary on main dashboard
- **Single-tenant simplification (May 20):** Root URL (`/`) redirects to `/induction/chat/{tenant_id}` so Greg opens browser and starts typing immediately. `/dashboard` shows full metrics. No tenant selection UI anywhere.
- **Scoring correction (May 20):** Initial induction gave 90/100 with 0 skills saved — LLM talked but never persisted. Fixed with: (a) `===SAVE_SKILL===` format front-and-center in system prompt, (b) module coverage requires concrete saved skills, not just LLM saying "done", (c) strict scoring rubric: 0-30 (useless) to 86-100 (comprehensive)
- **UI (Greg's feedback):** Induction page redesigned with tabbed interface (5 tabs: Overview, Proposition, GTM Learnings, Inbound Setup, Policy & Guardrails), skill-save toast animations (bottom-right, 3s fade), module completion confetti + celebrations, knowledge base summary on main dashboard

## Model Architecture

| Role | Model | Cost per M tok (in/out) |
|------|-------|------------------------|
| SDR conversations | DeepSeek V4 Flash | ~$0.50 / $2 |
| Induction/coaching | DeepSeek V4 Flash (current) | Claude Sonnet 4 planned for production |
| Heavy coding (prototype) | DeepSeek V4 Flash + V4 Pro | ~$0.50-$2 / $2-$8 |
| Voice pipeline | Hunar.ai (proprietary) | Per-minute |
| Utility code | Qwen Coder 14b (local) | Free |

## Pending Build Items
1. **SDR Engine** — Hook lead creation → trigger Hermes outreach via email/Telegram
2. **Skills Engine** — Web UI for viewing/editing skills + coaching conversation log
3. **Weekly Check-in** — Performance review conversation flow
4. **Telegram integration** — Use as WhatsApp proxy for lead conversations
5. **Voice stub** — Architecture for Hunar API integration
6. **Induction scoring severity** — Engine should be a hard grader; 90/100 for thin vague answers trains customer to be lazy. Module completion must be verified via persisted skills, not LLM self-report.

## Anti-Patterns
- ISA-only model (cash-flow negative — Masai School nearly died from this)
- AICTE/degree route (regulatory trap)
- Fixed voice scripts without dynamic generation
- Over-engineering V1: one agent, one channel proxy (Telegram), simple tools
- Building the dashboard before the agent works — agent FIRST, dashboard SECOND
