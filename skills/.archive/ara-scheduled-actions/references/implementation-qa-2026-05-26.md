# Cadence Logic — Implementation Q&A (May 26, 2026)

Design decisions from Greg's Q&A responses before building the cadence logic. These govern how the code behaves.

## Disqualification (Q1)
- Explicit "not interested" / opt-out → `lost` bucket
- Cadences excluded completely unless Greg says otherwise
- If asked to resume, Ava can remind: "This lead explicitly wanted to stop communicating"
- Ava can suggest a subtle approach but "keep your instincts strong — that is the agentic nature of Ava"

## Human Notification (Q2)
- ActionItem for dashboard
- Telegram/WhatsApp notification added later
- Exportable as JSON to any CRM

## Meeting Booking (Q4)
- "Let's meet Thursday" = meeting booked. Ava does NOT confirm the slot.
- Human notified: "meeting on Thursday" — confirm availability
- If confirmed, booked. Calendly deferred.
- Ava asks proactively: "Do you have another slot that works as a backup?"
- If human hasn't responded and lead follows up: "My manager has yet to confirm — apologies — would you have a few more slots?"
- If human silent: Ava acts agentically, notifies + emails human

## ICP / KB Broadness (QA)
- Be BROAD. Don't disqualify unless complete mismatch.
- KB + induction are the source of truth.

## Human Confirmation Timeout (QA)
- No timeout needed. If human hasn't responded: send notification + email to human.
- "Act agentically and figure it out."

## Multi-Ava (QA)
- Same logic across all Avas. Cadence is per-lead.

## Meeting Handoff Flow (Final Spec)
1. Lead says: "let's meet Thursday 3pm"
2. Ava says: "Great, let me check with my manager — do you have another slot that works as a backup?"
3. Human notified: "📅 Meeting requested: Thursday 3pm from [Lead Name]"
4. Human confirms or proposes alternative
5. Ava follows up with lead
6. If human silent: notification + email to human. Ava acts agentically.
