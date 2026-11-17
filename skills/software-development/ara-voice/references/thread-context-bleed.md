# Thread Context Bleed — Real Incident (2026-06-05)

## The Bug

User sent voice note: "add a note against Thomas George and tell him that the meeting's pushed to next week, change stage to meeting_booked, and set a reminder for Monday"

System responded with: "I heard: Update Thomas George (Swiggy) with note that meeting pushed to next week, change stage to meeting_booked, and set a reminder for Monday. Reply 'yes' to confirm."

User replied: "Yes - go ahead"

**Expected:** Execute the Thomas George updates.

**Actual:** "I couldn't send the WhatsApp to Rajesh — there was a system error."

## Root Cause Chain

1. **Keyword matching bug**: "Yes - go ahead" didn't match the exact-match tuple → fell through to normal coaching
2. **Thread context bleed**: The coaching thread had Rajesh Sharma conversation history (from ~10 hours earlier)
3. **Ava misinterpreted**: "set a reminder" → Ava thought "send a WhatsApp to Rajesh" (last discussed lead)
4. **No guardrails**: The execution prompt didn't prohibit WhatsApp sends

## The Three Fixes

| Issue | Fix | Type |
|-------|-----|------|
| "Yes - go ahead" not recognized | Regex prefix matching instead of exact tuple match | Code |
| Thread history bleeding | `thread_id=None` (fresh thread) instead of reusing coaching thread | Architecture |
| Ava sending unsolicited WhatsApps | Explicit "Do NOT send any WhatsApp messages to any lead" rule in execution prompt | Prompt |

## Key Lesson

**Prompt-level instructions to "ignore other context" are unreliable — you must use thread-level isolation.** Even if the keyword matching had worked, reusing the coaching thread would still allow Rajesh context to bleed in through the next phase. The thread isolation fix is the deterministic one.
