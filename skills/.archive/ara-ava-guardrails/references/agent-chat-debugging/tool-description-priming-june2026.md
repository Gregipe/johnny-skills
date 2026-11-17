# Tool Description Priming Causes Recurring Hallucinations

**Incident (June 15, 2026):** Ava repeatedly proposed "Daily Summary" cron jobs over 5 separate coaching sessions. Even after code-level fixes (enforcer, confusion fallback, voice note detection), the LLM kept hallucinating the same cron. Root cause: the tool description itself was priming the behavior.

## Root cause

The `set_cron` tool's AGENT_TOOL_SCHEMA entry contained prescriptive, action-oriented language:

```python
# ❌ BEFORE — primes the LLM to suggest daily summaries
"set_cron": {
    "description": "Set a RECURRING schedule. Use for daily summaries, recurring reminders. "
                   "Args: {\"title\": \"...\", \"message\": \"__morning_briefing__\" "
                   "(use this for dynamic daily summaries, pulls live action items), ...}"
}
```

Three priming elements:
1. **"Use for daily summaries"** — tells the LLM WHAT to build with this tool
2. **`__morning_briefing__`** — gives the exact magic string to pass
3. **"(use this for dynamic daily summaries, pulls live action items)"** — sells it as a feature

Every time the LLM saw this tool in context, it pattern-matched to "I should set up a daily summary."

## Fix

Replace all prescriptive language with conditional, permission-based language:

```python
# ✅ AFTER — no priming, only describes what the tool does
"set_cron": {
    "description": "Set a recurring scheduled action. Use ONLY when the user explicitly "
                   "asks for a recurring/daily/weekly schedule. Args: {\"title\": \"...\", "
                   "\"frequency\": \"daily|weekly\", \"time\": \"18:30\", \"message\": \"...\", "
                   "\"action_type\": \"whatsapp_to_owner\"}"
}
```

## Three layers of defense

| Layer | Mechanism | Purpose |
|---|---|---|
| 1. Tool description hygiene | No prescriptive language, no magic strings | Prevents LLM from being told WHAT to do |
| 2. "No extras" guardrail | Every tool call must map to a specific user request | Blocks proactive suggestions |
| 3. Confusion fallback | "When you don't understand, ASK — never guess" | Catches ambiguous messages that the LLM might pattern-match |

## Diagnostic pattern

When the same hallucination recurs across sessions despite code fixes:
1. Check the tool descriptions in AGENT_TOOL_SCHEMA for prescriptive language ("Use for X", "whenever you need Y", feature-selling)
2. Check for magic strings (`__morning_briefing__`, `__daily__`, etc.) that tell the LLM exactly what to pass
3. Check conversation history for prior instances of the hallucination (self-reinforcing context pollution)
4. Purge contaminated messages from the coaching thread after fixing the tool description