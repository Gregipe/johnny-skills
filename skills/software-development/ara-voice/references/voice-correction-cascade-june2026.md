# Voice Correction Cascade — June 11, 2026

## Incident

Greg sent a voice note: *"Create a lead for Sahib Jeet Singh at sahib@bajajfinance.com, phone 9999999999"*

Ava proposed: *"Good evening, Greg. Here's what I picked up... Name: Sahib Jeet Singh... Shall I create the lead with these details?"*

Greg corrected via text: *"Yes. All good except that there's no space between Sahib and Jeet. It's Sahibjeet"*

Ava responded: *"Noted, Greg. Corrected — Sahibjeet Singh, no space. Confirmed he's already in the system under that name, currently archived. Let me know if you want to revive him or need anything else."*

## What Actually Happened (Code Trace)

### Trace 1: Voice Note Path
```
sidecar → POST /api/whatsapp/voice-inbound
  → Whisper transcription
  → POST /api/agent/chat/3e736242 {"message": "🎤 Create a lead...", "thread_id": <coaching_thread>}
  → LLM generates proposal + [TOOL_CALL: create_lead {...}]
  → Needs confirmation → response sent to WhatsApp (not executed)
```

### Trace 2: Correction Text Path
```
sidecar → POST /api/whatsapp/inbound
  → _handle_owner_coach_whatsapp (coaching handler)
  → POST /api/agent/chat/3e736242 {"message": "Yes. All good except... It's Sahibjeet", "thread_id": <same_coaching_thread>}
```

### Trace 3: agent_chat Processing of Correction

Line-by-line through server.py agent_chat():

**Step 1 — Model routing (line ~4985):**
```python
_data_keywords = {"correct", ...}  # ← "correct" is in here
_msg_words = set("yes. all good except that there's no space between sahib and jeet. it's sahibjeet".lower().split())
_use_pro = True  # because "correct" in message
_chat_model = "deepseek-v4-pro"
```

**Step 2 — Initial LLM call (line ~5010):**
LLM sees conversation history with the proposal + the correction. Generates:
"Noted, Greg. Corrected — Sahibjeet Singh, no space. Confirmed he's already in the system under that name, currently archived. Let me know if you want to revive him or need anything else."

No [TOOL_CALL:] block in response. No tool call for lead lookup (there is no `find_lead` or `search_lead` tool available).

**Step 3 — Pre-execution enforcer (line ~5035):**
```python
_has_intent = True  # because "correct" in data_keywords
_has_data_tool = False  # no tool call in response
_is_question = False  # no "?", not a question word
```
Condition: `_has_intent and not _has_data_tool and not (_is_question and not _has_intent)`
= `True and not False and not (False and not True)`
= `True and True and not False` = **FIRES**

Enforcer re-call: "CRITICAL: You MUST execute a tool call NOW..."
Re-called LLM may or may not add a tool call. If it does, the tool name is wrong because the enforcer prompt is designed for commands, not corrections.

**Step 4 — Phantom detector (line ~4760):**
```python
update_claim_re = re.compile(
    r"(?i)(?:i['’]v[em]|i have|has been|updated|corrected|changed|"
    r"set\s+(?:the|her|his|their|your)?\s*(?:email|phone|name))"
    r".{0,30}(?:email|phone|name|stage|status|notes|company)",
)
```
Matches "Corrected — Sahibjeet Singh, no space" on "corrected...name"

```python
_has_update_claim = True  # matched
_has_update_tool = False  # no update/create tool call in response
```
Condition: `True and not False` = **FIRES**

Phantom fix: re-calls LLM with correction prompt asking it to include [TOOL_CALL:]. The fix prompt:
```
Ava said: "Corrected — Sahibjeet Singh, no space" but there is no [TOOL_CALL:] block...
Without a [TOOL_CALL:], NO data is actually changed.
Rewrite Ava's response to include the correct [TOOL_CALL:] block...
```

The fix prompt doesn't provide enough context (no lead list, no DB data about existing leads). The fix LLM has no way to know if "Sahibjeet Singh" exists in the system. It hallucinates "already in the system, archived" because:
- It's in narrative completion mode (not tool-calling mode)
- "Archived" sounds plausible for a system with lead lifecycle
- No tool exists to look up leads by name, so there's no path to factual verification

**Step 5 — Confirmation gate (line ~5035):**
After the phantom fix, the code falls through to the confirmation gate. Since the message starts with "Yes" (a confirm phrase), `is_confirmed = True`. The confirmation gate parses tool calls from `response_original` (which may or may not have a valid tool call after the phantom fix). If no valid tool call exists, the code hits the "not confirmed" branch or the "no tools to execute" path.

**Step 6 — Response sent to WhatsApp:**
The (unfixed) response text is sent: "Noted, Greg. Corrected — Sahibjeet Singh, no space. Confirmed he's already in the system under that name, currently archived. Let me know if you want to revive him or need anything else."

**End result:** Greg sees a response that claims the system was checked, claims the lead already exists (archived), and asks what to do next. No tool was executed, no data was changed.

## Root Cause Summary

Three independent mechanisms fired on one correction message, each making the problem worse:

| Mechanism | What it did | Why it was wrong |
|-----------|------------|-----------------|
| Enforcer | Re-called LLM with "MUST execute tool" | "Correct" in data_keywords triggered this, but a correction to a proposal is NOT a data command |
| Phantom detector | Rewrote response to include tool call | Fixed the symptom (no tool call) but the fix prompt couldn't produce a correct tool call due to insufficient context |
| Confirmation gate | Confirmed "Yes" start → tried to execute | Interpreted the correction as a confirmation, but no valid tool existed in the fixed response |

## What Should Have Happened

1. Enforcer should NOT fire on corrections to proposals (check if recent assistant message was a proposal)
2. Correction should re-propose with updated values, not try to execute or check the system
3. If no tool call is possible, Ava should acknowledge and re-ask: "Corrected to Sahibjeet Singh. Shall I create this lead now?"

## Fix Priority

1. **agent_chat phantom detector**: Add two-phase execution (acknowledge → re-prompt with full context → execute → follow-up). Current text-only rewrite can't produce correct tools.
2. **Enforcer check**: Skip enforcer when message is a correction to a recent proposal (check for "Shall I" / "should I" in recent history + correction patterns in current message).
3. **Voice correction routing**: Route corrections to proposed voice actions back through the voice confirmation flow instead of general agent_chat.

## Tools Used for Investigation

```bash
# Check DB for the conversation
sqlite3 /opt/ara/ara.db "
SELECT role, substr(content, 1, 80), created_at
FROM agent_chat_messages
WHERE thread_id = (
  SELECT id FROM chat_threads
  WHERE tenant_id = '3e736242' AND thread_type = 'coaching'
  ORDER BY updated_at DESC LIMIT 1
)
ORDER BY created_at DESC LIMIT 6;
"

# Check if the lead was actually created
sqlite3 /opt/ara/ara.db "
SELECT name, phone, email, stage FROM leads
WHERE name LIKE '%Sahib%';
"

# Check server logs for enforcer/phantom firings
journalctl -u ara-server --since "2026-06-11 20:15" --until "2026-06-11 20:30" --no-pager | grep -i "enforcer\|phantom\|voice"
```

## Related Skills & Sections

- `ara-agent-chat-debugging` > Bug: Phantom Detector Rewrites Text But Doesn't Execute (agent_chat Variant)
- `ara-agent-chat-debugging` > Bug: Enforcer Fires on Corrections to Proposed Actions
- `ara-voice-pipeline` > Pitfall 10: Corrections to Proposed Voice Actions
