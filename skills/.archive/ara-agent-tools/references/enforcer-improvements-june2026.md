# Enforcer Improvements — Question Detection & Interim Messaging (June 10, 2026)

## What Changed

Three improvements to the pre-execution enforcer after user reported ~30s dead air on a "can you set cron jobs?" request:

### 1. Question detection now uses substring matching (not just startswith)

**Before:** `_is_question = "?" in msg or _msg_lower.strip().startswith(("can", "could", ...))`

Failed for: `"🎤 hey eva, could you set a reminder"` — starts with "hey" not "could". Also failed for: `"Hey Ava - can you set cron jobs now?"` — starts with "Hey", not "can".

**After:** 3-layer detection:
1. `"?" in msg` — catches standard questions
2. Startswith after emoji strip — catches clean question starts
3. Substring match: `any(" " + w + " " in " " + _msg_clean[:60] + " " for w in ("can", "could", ...))` — catches "hey **could** you..." and "hey **can** you..."

### 2. Interim WhatsApp message when enforcer fires

When the enforcer does fire (a genuinely slow path), it immediately sends `"Ava is thinking..."` via WhatsApp so the user sees progress. The interim message is permanent (unlike the transient typing indicator which WhatsApp times out after ~20-30s).

### 3. Re-call prompt includes specific tool list

The old prompt (`"You MUST include a tool call"`) caused the LLM to respond with "Let me check the logs" instead of actually calling the tool. The new prompt lists available tools and gives a context-appropriate example.

## User Feedback Signal

Greg was explicit about UX tolerance:
- "I cannot have dead silence for 6-7 seconds"
- "I want some kind of interim iteration or thought process"
- "The user should be able to understand its thought process in basic English"

**Rule of thumb:** If total processing exceeds ~3s, the user needs SOME visible signal. The typing indicator covers 3-20s. The interim text message covers 20s+. Both should be present.

## Re-check After Re-call (Added Mid-Session June 10)

The enforcer now re-evaluates `_has_tool` after the re-call:

```python
try:
    response = call_llm(messages, model=_chat_model)
    _has_tool = "[TOOL_CALL:" in response
    if not _has_tool:
        logging.getLogger("ara").warning(
            f"Pre-execution enforcer: re-call still has no tool call."
        )
except Exception:
    logging.getLogger("ara").error("Pre-execution enforcer re-call failed")
```

**Why:** Before this fix, the enforcer re-called the LLM, replaced `response` with the re-call output, but never re-checked whether the new response actually contained a tool call. The code fell through to tool parsing with a tool-less response. This caused the second attempt on "Can you set cron jobs?" to reply "Yes, I can set recurring cron jobs now!" — sounding like it had done something, but no tool was ever called.

**Key behaviors:**
- **Single re-call only** — never loops. If the re-call still has no tool call, log and proceed.
- **`_has_tool` is re-assigned** — the original `_has_tool = "[TOOL_CALL:" in response` sits before the `if` block. After the re-call, `_has_tool` is re-set so downstream code uses the updated value.
- **Not an infinite loop** — The 95% rule says: if one re-call doesn't produce a tool call, either the toolset is incomplete or the request isn't actionable. Logging the gap and proceeding is correct.

## Data-Tool-Only Check (Added June 10)

**Problem:** The enforcer checked `"[TOOL_CALL:" in response` — this accepted ANY tool call, including diagnostic tools like `read_logs`. The LLM would call `read_logs` to investigate instead of calling `set_cron` to execute. The enforcer saw `[TOOL_CALL: read_logs]` and said "good, has a tool call" — the wrong tool satisfied the enforcer.

**Fix:** Check for data-modifying tool names specifically:
```python
_data_tools = ["set_cron", "set_reminder", "create_lead", "update_lead", 
               "create_deal", "send_whatsapp", "send_email", ...]
_has_data_tool = any('"tool": "' + t + '"' in response for t in _data_tools)
```

The re-call path also uses the same check — prevents the LLM from re-calling `read_logs` as a workaround.

**Root cause chain that led to this fix:**
1. System prompt had: "If a tool returns an error: diagnose with read_logs and tell the user"
2. Conversation history showed past cron failures
3. LLM concluded "there was a past error → I should investigate → call read_logs"
4. Enforcer saw [TOOL_CALL: read_logs] → skipped → read_logs executed → LLM got log output → said "Let me check the logs"
5. User never got their cron

**Fix was THREE-layer:**
1. **Prompt discipline** — "Call the data tool FIRST. Never investigate before executing."
2. **Data-tool-only enforcer** — `read_logs` no longer satisfies the enforcer
3. **Re-call prompt** — "DO NOT investigate. JUST DO IT." with narrowed tool list

## Hallucination Contagion (Discovered June 10)

**Problem:** When the LLM hallucinated "the cron tool hit a system error", that response was saved to the conversation history. On the next turn, the LLM read its OWN hallucination and repeated it — "Yes, the cron tool hit a system error again." Each duplicate voice note reinforced the belief.

16 duplicate voice notes + 7 hallucinated responses accumulated in 3 days.

**Fix:** Two-layer:
1. Delete hallucinated responses from DB conversation history
2. Add prompt rule: "If your previous response said a tool 'failed' — IGNORE that. The tool IS working now."

**Warning:** LLMs treat past responses as authoritative evidence. A single hallucinated error message in history can infect all subsequent turns about the same topic. Always clean the history AND add a prompt override.

## Related

- `ara-voice-pipeline` → `references/voice-interim-question-detection-june2026.md` — voice-specific details
- `ara-agent-tools` SKILL.md → Pre-Execution Enforcer section (updated)
