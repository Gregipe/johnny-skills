# Cadence Logic & Stage Design (May 2026)

> Synthesized from two design sessions with Greg. Reference for implementing cadence-based lead outreach, stage advancement, channel switching, and meeting booking.

## Stage Pipeline

```
new ──→ contacted ──→ engaged ──→ qualified ──→ meeting_booked ──→ [HUMAN TAKES OVER]
                               ↑                      ↓
                           dormant ─────────── closed_lost / closed_won
```

**Ava's ceiling:** `meeting_booked`. After that, all outbound stops and human takes over.

## Stage Advancement Rules

### `engaged → qualified` (Automated)

**Two criteria (both must be true):**
1. **Genuine interest/relevance** — lead has shown they're actually interested
2. **ICP fit** — lead broadly fits the configured use cases / ICP per KBs + induction

**Evaluation:**
- LLM-judged within KB/ICP guardrails. The KBs and ICP config make it systematic.
- **Broad qualification** — don't disqualify unless a *complete* mismatch
- If uncertain → flag for human double-check via ActionItem + notification (Telegram/WA later, exportable as JSON to CRM)

### Disqualification

- **"Not interested, stop contacting"** → `lost` bucket immediately. Ava can remind the human the lead opted out if they ask to resume.
- **Misclick / wrong link** → stays in `engaged` (not lost, not qualified)
- **Excluded from all future cadences** — unless the customer explicitly asks to resume. Ava can suggest a subtle re-engagement but must note the opt-out history.

### `qualified → meeting_booked`

**Clear intent signal required:**
- "Let's demo", "meet your team", "come by the office", "schedule a call"
- NOT "call me later" (that's still `qualified`)
- NOT vague interest

**After meeting booked:**
- ALL outbound cadences stop immediately
- Human takes over and attends the meeting
- Meeting outcome (won/lost) handled outside Ava's scope

### Meeting Booking Flow (Human-Coordinated)

1. Lead says "let's meet Thursday 3pm"
2. Ava says: *"Great, let me check with my manager — do you have another slot that works as a backup?"*
   - Asks for backup slot **proactively** (doesn't wait for human to respond first)
3. Human gets notified: "🔔 Meeting requested: Thursday 3pm from [Lead Name]" (ActionItem + notification)
4. Human is also emailed if they don't respond
5. If human hasn't responded and lead follows up: *"My manager has yet to confirm — apologies. Would you have a few more slots that work for you?"*
6. Human confirms or counter-offers → Ava follows up
7. **Ava does NOT confirm/cancel meeting slots independently.** She holds the loop open.
8. If human is silent indefinitely: Ava acts agentically — keeps the conversation warm, nudges the lead, figures it out.

**Calendly integration deferred.** Later: build a Calendly for Ava on her email. Also consider flashing the human's calendar. This should be asked about in induction and configured via Settings.

**Meeting link detection strategies (deferred):**
- Calendly webhook
- Message content detection ("let's meet Thursday")
- Any of the above is sufficient threshold

## Channel Switching Rules

### Core Principle
Templates = **no-reply path only**. Once a lead responds, cadence templates are void. Ava goes agentic.

### Per-Channel Behavior After Engagement

| Channel | Role | Behavior |
|---------|------|----------|
| Original response channel | Primary engagement | Respond here, nudge toward meeting |
| Multiple channels active | Multi-thread | Stay where reply frequency is highest. **Consistent messaging across channels — non-negotiable.** |
| Email | Preferred formal channel | Migrate here for long-form formal communication. "I'll continue on email, please check." |
| WhatsApp | Nudge/short-form | "I've sent you an email, could you reply there?" Only if email reply >48h, keep nudging via WhatsApp. |

### Switching Rules
1. Lead replies on WhatsApp → stay on WhatsApp, nudge toward meeting
2. Lead replies on both → where frequency is highest; migrate to email eventually
3. Lead stops replying on WhatsApp but email is active → consistent messaging on both
4. If email reply >48h silent → WhatsApp nudge: "I sent an email, could you check?"

## No-Reply Protocol (Post 7-Day Silence)

- **Dignified only** — no spamming
- 1 email + 1 WhatsApp per week, alternating: Email→WA→Email→WA
- Ava decides timing and content
- No template-based cadence restart — Ava acts agentically

## Dormant Re-engagement

### Detection
- 30 days of inactivity → auto-marked as `dormant` (existing `_check_dormant`)

### Re-activation Rules

| Previous state | Lead says | Move to |
|---------------|-----------|---------|
| Any | Legitimate reason (health emergency, travel, etc.) | **Original stage** they were in before dormant |
| Any | Trivial reply ("just catching up") | **Engaged** |
| Was `qualified` | Meaningful re-engagement | Can go to **qualified** (Ava's discretion) |
| Was `qualified` | Ambiguous re-engagement | **Engaged** (default) |

**Default re-activation stage:** `engaged`. Going straight back to `qualified` is only for clear cases.

## Post-Qualification Cadence

After `qualified` → Ava's sole objective is **book the meeting**:
- Value prop reinforcement
- "Love to get on a quick call / grab a coffee / do a demo"
- Soften the path to meeting

## Per-Lead Customization

- Templates are global. Normally no override needed.
- After any response → templates void. Ava goes fully agentic toward meeting booking.
- Post-qualification → full tunnel vision on meeting booking.

## Channel Execution Status

| Channel | Status |
|---------|--------|
| **WhatsApp** | ✅ Working |
| **Email** | ✅ Configured — test hook pending (deferred to later build) |
| **Call reminders** | ❌ Needs agent creation with specific prompt (deferred) |

## Multi-Ava (Multi-Tenant Edge Case)

- Same cadence logic across all Avas
- Cadence is per-lead, not per-Ava

## Configuration Architecture

Not a flat markdown rules file. Three layers:
1. **Parameterized config** — tenant `config` field for timing, thresholds, channels
2. **Code-enforced rules** — stage transitions, disqualification, channel consistency, scheduling gates
3. **LLM-judged within guardrails** — ICP fit, intent detection, re-engagement classification

## Human Notification Pattern

When Ava needs human attention:
1. **ActionItem** created in DB (action_type: `stage_change`, `escalate`, `suggest_deal`, `meeting_request`)
2. **LearningNotification** for bell icon
3. Later: **Telegram / WhatsApp** message to the human
4. All exportable as **JSON** to whatever CRM the human uses

## Build Order

1. **`engaged → qualified`** — code the advancement evaluation using KBs + ICP + lead responses
2. **Disqualification handling (`lost` bucket)** — auto-move + cadence exclusion
3. **Post-engaged scheduling fix** — stop scheduling cadence steps for engaged+ leads (Ava handles them)
4. **Post-engaged agentic behavior** — update Ava's prompts for meeting-nudging
5. **`qualified → meeting_booked`** — meeting intent detection + human notification flow
6. **Dormant re-engagement (improved)** — smart stage restoration on inbound
7. **Channel switching rules** — add to Ava's prompt
8. **7-day silence resume** — post-silence protocol
9. **Email hook testing** — deferred
10. **Calendly integration** — deferred

## Design Questions to Ask Before Building Cadence Logic

(For use during Phase 1 Q&A — ask these before any code)

1. **Qualification criteria** — what signals qualify a lead? (KB-defined? LLM-judged? Human confirms?)
2. **Disqualification handling** — auto-lost on explicit opt-out? Exclude from future cadences? (Answer: yes to both.)
3. **Meeting booking** — Calendly? Human-coordinated? Auto-detect intent from message content? (Answer: human-coordinated for now, Calendly deferred.)
4. **Channel switching threshold** — how many days of silence before switching? Which channel is preferred?
5. **Dormant threshold** — how many days of inactivity = dormant? 30 days? (Answer: current 30d works.)
6. **Post-silence protocol** — how often to reach out after silence? What channels? (Answer: 1 email + 1 WA per week, alternating.)
7. **Multi-Ava** — per-lead cadence (shared) or per-Ava (separate)? (Answer: shared.)
8. **Email sending** — wired up yet? Needs testing? (Answer: configured, test deferred.)
9. **Human notification** — how does the human get notified of actions? (Answer: ActionItem + notification + eventually Telegram/WA.)
