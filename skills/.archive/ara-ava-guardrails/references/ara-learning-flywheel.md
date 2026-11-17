# ARA Learning Flywheel

> **Source:** This content was merged from the now-deprecated `ara-learning-flywheel` skill. The authoritative reference is now `ara-ava-guardrails`.

## Core Design Principle

> "Ava improves with every conversation like a human. Every single day, every single conversation, Ava gets better — just like an SDR in their 45th conversation is significantly better than their 1st, and their 100th is better than their 45th."

## Architecture: 4-Layer Pipeline

```
Lead Conversation (any channel: WhatsApp, Email, Call)
        ↓
Layer 1: Insight Extraction  → AvaInsight (per-conversation learnings)
        ↓
Layer 2: Skill Promotion      → Skill (cross-threshold patterns, auto-promoted)
        ↓
Layer 3: Weekly Synthesis     → Strategic skills (LLM connects granular → broad)
        ↓
Layer 4: Human Review Loop    → Approve / Refine / Reject with coaching
        ↓
Layer 0 (always active): System Prompt Injection → Ava pre-loaded with learned patterns
```

### Layer 0: System Prompt Injection (Pre-emptive Intelligence)

When a new lead conversation starts, Ava's system prompt is augmented with relevant skills for that lead profile BEFORE Ava says anything. Skills are now **segment-filtered** — only skills relevant to the lead's segment are injected.

**Critical — TWO injection points, not one:**
1. **Agent Chat** — skills_context injected into system prompt
2. **Scheduled Message Generation** — `_generate_step_message()` must also receive skills

### Layer 1: Insight Extraction (Every Conversation)

At the end of every lead interaction, Ava parses the conversation for:
- Objections raised
- Sentiment trajectory
- Decision maker signal
- Segment matching
- Engagement timing
- Pricing friction
- Intent detected
- Communication style

### Layer 2: Skill Promotion (Auto, Threshold-Crossing)

When 5+ insights share a normalized key with consistent value, confidence crosses threshold (0.70) and a Skill is auto-created:
- 0.70 → auto-promote to Skill (5+ confirmations)
- 0.85 → max confidence without human verification
- 0.15 → base per single insight
- Decay: −5%/month without reinforcement

### Layer 3: Weekly Synthesis

Scheduled run where Ava:
- Collects all granular skills with confidence > 0.5
- LLM creates "strategic" skills that connect multiple small learnings
- Flags for human review

### Layer 4: Human Review Loop

- Dashboard view with skill counts and confidence metrics
- Skill list view (filterable, searchable, categorized)
- Skill detail view with evidence drilling
- Approve / Refine / Dismiss buttons

## The 5 Learning Pillars

From every conversation, Ava draws:
1. **Objection Patterns** — What objections come up per segment?
2. **Speed-of-Response Correlation** — Does faster response increase meeting rate?
3. **Segment × Pain Point Mapping** — What value proposition resonates per industry × size?
4. **Decision Maker Profiling** — Which designations have authority?
5. **Pricing Sensitivity by Segment** — Correlation between company size/industry and pricing concerns.

## Two-Layer Architecture

### Tenant Layer
Each tenant's Ava gets better at THEIR leads, THEIR pricing, THEIR objections.

### Platform Layer (Feedback Triage)
Ava has a `log_feedback(category, title, description, impact)` tool. Central agent polls and clusters feedback across tenants.

## API Endpoints (Live)

| Route | Purpose |
|-------|---------|
| `GET /api/learning/stats` | Dashboard summary |
| `GET /api/skills` | List skills |
| `GET /api/skills/{id}` | Skill detail with evidence |
| `PATCH /api/skills/{id}` | Human review |
| `POST /api/learning/promote` | Trigger skill promotion |
| `POST /api/conversations/{id}/extract-insights` | Trigger insight extraction |
| `POST /api/learning/synthesize` | Trigger weekly synthesis |

## Build Status (May 2026)

All phases are LIVE:
- ✅ Schema (Skill columns, SkillEvidence, LearningNotification)
- ✅ Backend (promotion, extraction, APIs)
- ✅ Learning UI (nav, dashboard, skills list, detail)
- ✅ Notifications (bell icon, dropdown)
- ✅ Weekly synthesis

## See Also

- `ara-ava-guardrails` skill — authoritative reference for Ava's intelligence system
- Original source: `productivity/ara-learning-flywheel/SKILL.md`
