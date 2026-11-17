# Known Limitations — ARA Scheduled Actions & Cadence System

Audited May 26, 2026. These are design gaps, not bugs. Any session modifying Ava's auto-response, inbound handling, cadence builder, or lead management should account for these.

## 1. ActionItems Have No UI

`ActionItem` records are created by `evaluate_qualification`, `mark_meeting_booked`, dormant re-engagement, lost re-engagement, and the original `_check_and_create_action_items()` — but there are **no API endpoints** to query them and **no frontend** to view/dismiss/resolve them.

**Impact:** Qualification flags, meeting requests, and re-engagement alerts go into the DB but are invisible to Greg. The human-in-the-loop feedback is broken — Ava flags things but no one sees them.

**Fix scope:**
1. Add `GET /api/action-items` — list open items (type filter, lead filter, limit/offset)
2. Add `PATCH /api/action-items/{id}` — resolve/dismiss
3. Frontend: Add "Needs Review" section to the Actions page in the dashboard, with a toggle between "Scheduled" (current ScheduledAction timeline) and "Needs Review" (ActionItems)
4. Wire the red badge on the Actions nav item to count open ActionItems

## 2. Email Hook Untested

`send_via_gmail_api()` and SMTP are wired in `_execute_action()` for email-type actions, and silence resume schedules emails — but the flow has never been tested end-to-end. Gmail OAuth flow exists but may need a test send to validate.

**Impact:** Email steps in cadences and silence resume email follow-ups will silently fail or do nothing.

**Fix:** Send a test email via the API or trigger a silence-resume email for a known lead and verify delivery.

## 3. Meeting Booking — No Calendly / Calendar Integration

`mark_meeting_booked` notifies the human but doesn't:
- Auto-book a calendar slot
- Check human's calendar for availability
- Send a Calendly link to the lead
- Flash the human's calendar for confirmation

**Current behavior:** Ava asks for backup slots proactively. If human confirms, she tells the lead. If human silent, Ava acts agentically. The actual booking is manual.

**Deferred per Greg.** Build Ava's Calendly or flash human's calendar later.

## 4. Call Reminders Not Wired

The cadence UI allows "Call" steps and `_execute_action` handles `call_reminder` by creating a LearningNotification — but there's no agent/voice-calling integration. Greg will set this up later.

## 5. Scheduler Uses 30s Polling

Works fine for daily/hourly steps but introduces 0-30s jitter for immediate first-step actions. Acceptable for current scale.

## 6. No Cadence Versioning

`CadenceConfig` is overwritten on every publish. No rollback. Acceptable for single-tenant.

## ✅ Resolved (May 26, 2026)

| Limitation | Fix |
|------------|-----|
| No stage transition on inbound reply | ✅ Inbound reply moves `new/reached_out` → `engaged`. `dormant` → smart re-engagement. |
| No `first_reply_at` field | ✅ Added to Lead model. Set on first inbound. |
| No `engaged → qualified` auto-advancement | ✅ `evaluate_qualification` tool with broad ICP/KB matching. |
| No `qualified → meeting_booked` detection | ✅ `mark_meeting_booked` tool with human notification. |
| No `lost` bucket / disqualification | ✅ `lost` stage cancels cadences, excludes from scheduling. |
| Engaged leads still received cadence steps | ✅ `engaged` added to scheduler skip list. Post-engagement is agentic. |
| Dormant leads always went to `engaged` | ✅ Smart re-engagement: checks deal stage, restores to `qualified` if applicable. |
| No 7-day silence resume | ✅ `_check_silence_resume()` alternating email↔WhatsApp weekly. |
| No post-engagement meeting nudging in prompts | ✅ Added to both `AVA_AUTO_SYSTEM_PROMPT` and `AGENT_SYSTEM_PROMPT_BASE`. |
