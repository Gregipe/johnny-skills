# ARA / Ava Capability Audit — June 2026

Session date: June 1, 2026
Trigger: Greg asked "think through what else we should build to make Ava a world-class self-autonomous SDR agent"
Method: Codebase surface mapping via server.py (8429 lines)

## Current Capabilities

### Lead Management (Solid)
- CRUD: create, update, search, bulk-assign, bulk-delete, CSV upload, duplicate check
- Lead stages: new/reached_out/engaged/qualified/meeting_booked/proposal/closed_won/closed_lost/dormant/lost/archived
- Auto-qualification from conversation signals
- Cadence type auto-detection from source
- Notes, product interest, assigned agent fields

### Deal Management (Solid)
- CRUD with events/activity log
- Stage: new/reachout/negotiation/closing_won/lost
- Expected value, contact info, industry segment
- Attach/detach leads from deals
- Auto-sync deal stage from lead

### WhatsApp Outreach (Working)
- Send to leads (resolved by name)
- Schedule messages with delay
- Send to owner for coaching/test
- Cadence engine: cold/inbound/nurture templates with scheduling
- Cadence trigger, pause, debug (dry-run)
- Cadence auto-stops on lead engagement

### Email (Partial)
- Send immediate email via Gmail
- Schedule email with delay
- Gmail OAuth integration (wired but requires setup)

### Pipeline Intelligence (Working)
- Pipeline summary (deals by stage, total value)
- Activity log per lead or deal
- Lead detail with full profile
- Conversation history with lead

### Learning System (Working)
- Save learnings as skills (proposition, gtm_learning, guardrail, objection_pattern, etc.)
- Knowledge base search
- Insight extraction from conversations
- Watchlist for contradictions, learnings, coaching tips
- Learning notifications with acknowledge
- Document upload and knowledge extraction

### Coaching (Working)
- WhatsApp coaching thread via agent chat
- Watchlist-driven coaching moments
- Blunt feedback personality
- System prompt builder with brand voice / sector / guardrails

### System/Admin (Working)
- Tenant management, settings, segments
- Log reading, cadence debug tools
- UI: dashboard with leads/deals/knowledge/activity pages
- Threaded chat (ChatGPT-style)

### Action Items & Reminders (Working)
- Create action items with priority (low/normal/high/critical)
- List/filter by status
- Cancel scheduled actions
- Escalation with urgency levels

## Key Gaps Identified

### Tier 1 — Core SDR Functions

| Feature | Impact | Moat? |
|---------|--------|-------|
| Meeting Scheduling (Calendar) | Core — closes the loop on outreach | Table stakes |
| Voice Calling | Core — Hunar.ai is a voice AI company | Moat |
| LinkedIn Outreach + Sourcing | Core — B2B primary channel | Table stakes (need it to compete) |

### Tier 2 — Smart Automation

| Feature | Impact | Moat? |
|---------|--------|-------|
| Adaptive Cadence (engagement-responsive) | Growth — improves conversion | Potential moat |
| Reply Intent Classification | Growth — enables analytics + smart routing | Table stakes |
| Multi-Channel Sequencing | Growth — LinkedIn→Email→WhatsApp→Call | Table stakes |
| A/B Testing on Outreach | Growth — self-improving | Potential moat |

### Tier 3 — Coaching & Intelligence

| Feature | Impact | Moat? |
|---------|--------|-------|
| Role-Play / Simulation Mode | Quality — unique coaching differentiator | Moat |
| Performance Analytics / WBR | Quality — closes feedback loop | Table stakes |
| Deal Coaching (proactive) | Quality — saves deals | Potential moat |

### Tier 4 — Infrastructure

| Feature | Impact | Moat? |
|---------|--------|-------|
| Call transcription + analysis | Quality | Complementary |
| Competitive intelligence | Quality | Potential moat |
| CRM sync (Salesforce/HubSpot) | Growth | Table stakes |

## Build Order Recommended

| Priority | Feature | Why | Tier |
|----------|---------|-----|------|
| 1 | Meeting Scheduling (Calendar) | Closes the biggest blocker — lead says yes, nothing happens | Core |
| 2 | Voice Calling | Your moat. Voice AI company not using voice = missed identity | Moat |
| 3 | LinkedIn Outreach + Sourcing | Opens new pipeline channel. B2B bread and butter | Core |
| 4 | Role-Play Mode | The "coach" superpower — no tool does this well | Moat |
| 5 | Reply Intent + Analytics | Closes feedback loop so both improve over time | Growth |

## Rationale for Priority 1 (Meeting Scheduling)

The single biggest gap is the handoff from "lead is interested" to "meeting is on the calendar." Everything Ava does in outreach leads to this moment, and today it's a dead end. Integrating Google Calendar enables:
1. Ava detects meeting interest → checks Greg's availability
2. Proposes 2-3 time slots
3. Lead picks one → Ava creates calendar event + Google Meet link
4. Sends confirmation to both parties
5. Sets reminder in Ava's system

This also enables proactive debrief after the meeting ("How did the demo go? What did they say about pricing?").
