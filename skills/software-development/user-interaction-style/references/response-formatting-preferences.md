# Response Formatting Preferences (June 2026)

Greg explicitly rejected the old style of raw dumps and unstructured responses.
He wants responses that are clean, scannable, and organized.

## Section Headers
Use bold for all section headers: `*Header Name*` for WhatsApp/plain-text channels.
Never use emoji-only lines without text.

## Action Items — Always Show Three Things
Every action item MUST include:
1. **Description** — what needs to be done
2. **Lead** — who it's for (tagged with "— Lead Name")
3. **Due date** — when it's due (tagged with "⏰ Date Time")

Example: `• Check in on team — Prashant Rai | ⏰ Jun 17 at 7:00 PM`

## Multi-Item Section Order
When presenting multiple types of items, use sections in this order:
1. `*🔴 OVERDUE*` — past due, not completed
2. `*⏳ PENDING*` — upcoming or in progress
3. `*✅ ACCOMPLISHED*` — completed today
4. `*📚 LEARNINGS*` — today's learning notifications only

## Status Icons
- ✅ completed / resolved
- ⏳ pending / in progress
- 🔴 overdue (past due date, not completed)

## Multi-Step Plans
Numbered steps with bold headers:
```
**Step 1/3:** Create deal
**Step 2/3:** Attach contact
**Step 3/3:** Set reminder
```

## Anti-Patterns
- No ASCII art
- No emoji-only lines without text
- No more than one blank line between sections
- No walls of text without structure
- No raw dumps of database IDs or status codes

## Prompt Section
The system prompt section "Response Formatting (HARD RULE)" at line ~5398 in server.py enforces these rules at the LLM level.
