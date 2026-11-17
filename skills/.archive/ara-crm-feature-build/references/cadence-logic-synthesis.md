# Cadence Logic — Full Design Synthesis (May 2026)

> The complete design conversation with Greg, capturing every decision. Written during a deep-dive session covering all 8 gaps in the original cadence system.

## Stage Pipeline & Ava's Role Boundary

```
new ──→ contacted ──→ engaged ──→ qualified ──→ meeting_booked ──→ [HUMAN TAKES OVER]
                              ↑                      ↓
                          dormant ───────────── closed_lost / closed_won
```

**Key boundary:** `meeting_booked` is Ava's ceiling. Once a meeting is booked, all cadences stop and the human takes over. Ava does not participate beyond that point.

---

## 1. `engaged → qualified` Advancement

### Signals
Two things must be true:
1. **Interest/relevance** — lead has shown genuine interest in what we offer
2. **ICP fit** — lead broadly fits the configured use cases / ICP

### Disqualification
A lead who replied but clearly doesn't fit (e.g., recruiter clicked recruitment link by mistake) stays in `engaged` — they've replied but are not qualified.

### Mechanism
- Ava evaluates based on: **lead responses** + **ICP definition** + **induction knowledge bases** + **tenant config**
- This is inherently subjective — the KBs and ICP config are what make it systematic
- When uncertain → flag for human double-check (notify human operator)

### Edge cases
- Misclick / wrong link → `engaged`, not `qualified`
- Vague interest → Ava probes further before advancing

---

## 2. `qualified → meeting_booked` Advancement

### Signals
Clear intent to take things forward — not just "call me later" (which is still `qualified`), but:
- "Let's do a demo"
- "Can I meet your team?"
- "Come by the office"
- "Schedule a call to discuss"

### After meeting booked
- Ava stops all outbound comms
- Human takes over and attends the meeting
- Meeting outcome (won/lost) handled outside Ava's scope

---

## 3. Channel Switching Logic

### Core principle: templates only apply when silent
Cadence templates define the **no-reply** path. Once a lead responds, the template is off the table — Ava switches to agentic behavior.

### Per-channel behavior after engagement

| Channel | Role | Behavior |
|---------|------|----------|
| **Original response channel** | Primary engagement | Respond here, nudge toward meeting |
| **Multiple channels active** | Multi-thread | Stay where frequency is highest. Must keep messaging consistent across both. |
| **Email** | Preferred formal channel | Migrate here for long-form formal communication. "I'll continue on email, please check." |
| **WhatsApp** | Nudge/short-form | "I've sent you an email, could you reply there?" Only if email reply >48h, keep nudging via WhatsApp. |

### Switching rules
1. Lead replies on WhatsApp → stay on WhatsApp, nudge toward meeting
2. Lead replies on both → where frequency is highest; migrate to email eventually
3. Lead stops replying on WhatsApp but email is active → consistent messaging on both
4. If email reply >48h silent → WhatsApp nudge: "I sent an email, could you check?"

### Non-negotiable
**Consistent messaging across channels.** No contradicting yourself on WhatsApp vs email.

---

## 4. Reply → Cadence Resume (After Silence)

### 7-day rule
No reply after 7 days → Ava decides when to resume. **Dignified communication only** — no spamming.

### Post-silence protocol
- **1 email per week** + **1 WhatsApp per week** (alternating)
- Week pattern: Email → WhatsApp. Next week: Email → WhatsApp. Repeat.
- No template-based cadence restart — Ava acts agentically

---

## 5. Per-Lead Customization

### Default
Templates are global. Norm is not to override timing.

### After response
All template cadences are void. Ava pivots to **agentic nudging toward meeting booking**.

### Implication
Per-lead customization is handled by Ava's judgment, not by template overrides. If a lead has replied, Ava is already in custom mode.

---

## 6. Post-Qualified Cadence (Deal-Stage-Aware)

### After `qualified`
Ava's objective pivots to **booking the meeting** — full tunnel vision on:
- Value prop reinforcement
- "Love to get on a quick call / grab a coffee / do a demo"
- Soften the path to meeting

### After `meeting_booked`
- **All outbound stops immediately**
- Human takes over

---

## 7. Dormant Lead Re-engagement

### Re-activation rules

| Previous state | Lead says | Move to |
|---------------|-----------|---------|
| Any | Legitimate reason (health emergency, travel, etc.) | **Original stage** they were in before dormant |
| Any | Trivial reply ("just catching up") | **Engaged** |
| Was `qualified` | Meaningful re-engagement | Can go to **qualified** (at Ava's discretion)** |
| Was `qualified` | Ambiguous re-engagement | **Engaged** (default) |

**Default re-activation target:** `engaged`. Going straight back to `qualified` is only for clear cases.

---

## 8. Non-WhatsApp Execution

| Channel | Status |
|---------|--------|
| **WhatsApp** | ✅ Working |
| **Email** | ✅ Configured — need to test the hook |
| **Call reminders** | ❌ Needs agent creation with specific prompt — Greg will do later |

---

## How This Gets Configured

Not a flat markdown rules file. Three layers:

| Layer | Implementation |
|-------|---------------|
| **Stage advancement rules** (engaged→qualified) | Code logic with KB/ICP-driven evaluation. The "what qualifies" is configurable via ICP definition in tenant settings + induction KBs. |
| **Channel switching rules** | Hardcoded logic (well-defined switching conditions don't change per tenant) |
| **Timing rules** (7-day silence, post-silence protocol) | Configurable parameters per tenant (silence_days, email_frequency, etc.) |
| **Re-engagement logic** | Code logic with configurable stage mapping |
| **Ava's judgment calls** | LLM-driven within guardrails defined by the rules above |

---

## Build Order

1. **Email sending hook** — wire up the configured email for cadence execution (test first) — *deferred per Greg, not critical*
2. **`engaged → qualified`** — code the advancement evaluation using KBs + ICP + lead responses
3. **Post-engagement agentic behavior** — Ava's logic for nudging toward meeting after any response
4. **Channel switching** — implement the template-silent / multi-channel consistency rules
5. **Post-qualified cadence** — shift to meeting-booking objective
6. **7-day silence resume** — post-silence protocol
7. **Dormant re-engagement detection** — auto-advance from dormant on inbound
8. **Per-lead override UI** — if needed after everything else works

---

## Design Decisions From Q&A (Session 2)

### 1. Disqualification handling
- Explicit opt-out / "not interested" → `lost` bucket, excluded from cadences
- Ava can remind human the lead opted out if asked to resume
- Suggest subtle approach but *keep instincts strong* — that's the agentic nature

### 2. Human double-check UX
- ActionItem + LearningNotification for bell icon
- Telegram/WhatsApp notification added later
- Exportable as JSON to any CRM

### 3. Email hook → deferred
- Not critical now. Greg will come back to it.

### 4. Meeting booking
- Build a Calendly for Ava on her email (later)
- "Let's meet Thursday" → meeting booked. Ava doesn't confirm the slot.
- Human notified: "meeting on Thursday" — does it work?
- If confirmed, book it. Calendly deferred.
- Ava asks for backup slots proactively: "Do you have another slot that works?"
- If human hasn't responded and lead follows up: "My manager has yet to confirm — apologies — would you have a few more slots?"
- If human silent: Ava acts agentically, notifies + emails human

### 5. Multiple Avas
- Same logic across all. Cadence per-lead.

### 6. KB / ICP
- Broad evaluation. Don't disqualify unless complete mismatch.
- KB + induction are the source of truth.

### 7. Meeting booking flow — human handoff
Ava says: "Great, let me check with my manager — do you have another slot that works as a backup?"
Human gets notified with meeting request.
Human confirms or proposes alternative.
Ava follows up with lead.
If human doesn't respond in 24h+: notification + email to human. Ava acts agentically.
