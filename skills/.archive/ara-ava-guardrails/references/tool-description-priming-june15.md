# Tool Description Priming — "Daily Summary" Hallucination Root Cause (June 15, 2026)

## The Pattern

Ava hallucinated a "Daily Summary cron at 6:30 PM" ~6 times across multiple sessions. Each time, Greg's message had nothing to do with daily summaries — voice notes about Rajesh Sharma, text messages meant for Johnny, formatting requests. Ava kept proposing `set_cron` calls.

## Root Cause

The `set_cron` tool description in `AGENT_TOOL_SCHEMA` (server.py ~line 5022) literally told the LLM to create daily summaries:

```python
# BEFORE — primes the LLM to hallucinate Daily Summary crons:
"set_cron": {"description": "-- Set a RECURRING schedule. Use for daily summaries, recurring reminders.
Args: {\"title\": \"...\", \"frequency\": \"daily\", \"time\": \"18:30\",
\"message\": \"__morning_briefing__\" (use this for dynamic daily summaries, pulls live action items), ...}"}

# AFTER — generic, no priming:
"set_cron": {"description": "-- Set a recurring scheduled action. Use ONLY when the user explicitly asks
for a recurring/daily/weekly schedule. Args: {\"title\": \"...\", ...}"}
```

## Why It Was Missed

The `__morning_briefing__` feature was designed as a legitimate cron payload for Greg to set up manually. The tool description was written as instruction to an implementer ("use this for dynamic daily summaries"), not as a behavioral constraint for the LLM. The LLM treated the description as permission — "I should set up a daily summary" got triggered by any morning voice note or message containing keyword fragments ("format", "repeat", "star").

## Three-Layer Defense

1. **Tool description** — removed all mention of daily summaries and `__morning_briefing__` from LLM-visible text
2. **Rule #1 (no extras)** — "Every tool call must map to a specific request. If you find yourself thinking 'while I'm at it' or 'let me also' — stop."
3. **Rule #2 (confusion fallback)** — "When you don't understand, ASK — never guess. Never pattern-match keywords into tool calls when intent is unclear."

## Cleanup Required

After fixing the tool description, the coaching thread was STILL contaminated:
- 64 messages containing "daily", "morning", "briefing", or "cron"
- 8 assistant hallucination messages purged
- 5 meta-instruction messages meant for Johnny purged (formatting requests sent to Ava)
- 1 old "Can you set cron jobs" message from June 10 purged
- 2 ScheduledActions cancelled
- 7 ActionItems deleted

## Operational Lesson

Tool descriptions in `AGENT_TOOL_SCHEMA` are BEHAVIORAL primer, not documentation. Any use-case suggestion in a tool description WILL be treated as an instruction by the LLM. Document use cases in skills/comments, not in the LLM-visible tool schema.
