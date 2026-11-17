# Ava's 8-Layer Hallucination Defense Architecture

Built June 16, 2026 in response to systematic hallucination failures.

## Architecture

```
User message
    ↓
LAYER 1: Message Classification (7 types)
    CHITCHAT | SIMPLE_QUESTION | CAPABILITY | DIAGNOSTIC | ACTION | STRATEGIC | AMBIGUOUS
    → Determines whether to think or act. STRATEGIC/CAPABILITY blocks data tools.
    → Location: system prompt (AGENT_SYSTEM_PROMPT_BASE)
    ↓
LAYER 2: Reasoning Preamble
    "Got it — Greg wants X. I'll [1-2 sentence plan]."
    → Forces plan before tool selection. Prevents keyword-matching.
    → Location: system prompt, inserted after classification rules
    ↓
LAYER 3: Hard Guard (code-level)
    STRATEGIC/CAPABILITY modes block create_lead, create_deal, send_whatsapp, send_email, trigger_cadence
    → Even if the LLM tries to execute during analysis, the code refuses.
    → Location: _run_observe_loop, tool execution section (around line 5743)
    → Error code: BLOCKED_IN_ANALYSIS
    ↓
LAYER 4: Tool Execution with Validation
    - create_lead rejects "TBD", "Unknown", "N/A" placeholder names
    - create_action date-only defaults to 6 PM IST (12:30 UTC)
    - update_action parses string due_at to datetime, returns due_at in response
    - get_action_items returns action IDs [id=XXXXXXXX] for direct updates
    ↓
LAYER 5: Error Recovery + Mode Persistence
    - 4 recovery paths: fix syntax, switch tool, communicate gap, ask for missing info
    - Mode reminder re-injected every observe loop iteration
    - Failed tools → diagnosis prompt → "can you fix input and retry?"
    - Location: _run_observe_loop feedback section (around line 5788)
    ↓
LAYER 6: Confirmation Self-Audit
    Before every [ACTION: ASK], run 3-bullet check:
    1. TIME: Is the due time what Greg asked for?
    2. LEAD: Is this the right lead?
    3. GAPS: Am I missing anything? (attachment, channel, content, priority)
    → If any check fails, fix tool args BEFORE showing confirmation.
    → Location: system prompt (Execution Intent Protocol section)
    ↓
LAYER 7: Response Delivery
    Deliver final_text (LLM synthesis), not render_results (tool confirmations).
    "Here's the analysis..." not "✅ 9 actions completed."
    → Location: _run_observe_loop return
    ↓
LAYER 8: Memory
    save_memory / search_memory tools using skills table (category="memory")
    Auto-injected into system prompt (last 20, category="memory")
    Survives across sessions
    → Location: TOOL_SCHEMAS, execute_tool, agent_chat memory injection
```

## Timezone Handling

**Problem**: LLM passes IST times as-is, server treats all datetimes as UTC.
**Example**: "5 PM" → LLM passes "2026-06-16T17:00:00" → stored as 5 PM UTC = 10:30 PM IST.

**Fix**: System prompt now includes conversion table:
```
IST to UTC: SUBTRACT 5 hours 30 minutes
  9:00 AM IST  = 03:30 UTC
  5:00 PM IST  = 11:30 UTC
  6:00 PM IST  = 12:30 UTC
  10:30 PM IST = 17:00 UTC
```

## Common Failures Fixed

| Failure | Root Cause | Fix |
|---------|-----------|-----|
| create_action due time wrong | Date-only input defaulted to 9 AM UTC (2:30 PM IST) | Now: 6 PM IST (12:30 UTC) |
| update_action crashes | String due_at passed to SQLAlchemy DateTime column | Now: `datetime.fromisoformat(raw)` |
| update_action cascading fail | First crash poisons DB session → PendingRollbackError | Now: `db.rollback()` in except block |
| get_action_items no IDs | Output didn't include action_id → LLM couldn't update | Now: `[id=XXXXXXXX]` in output |
| TBD leads created | LLM created placeholder-named leads during STRATEGIC analysis | Now: create_lead blocks "TBD" names |

## MAX_TOOL_STEPS

Changed from 4 → 6. Penultimate step gets "synthesize now" prompt.
Location: _run_observe_loop
