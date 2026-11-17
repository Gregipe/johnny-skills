# Voice Correction Cascade — Sahibjeet Incident (June 11, 2026)

## Scenario

User sends a voice note proposing a new lead ("Sahib Jeet Singh, sahib@bajajfinance.com, 9999999999"). Ava correctly proposes with confirmation. User text-replies with a name correction ("All good except no space — it's Sahibjeet"). Ava responds: "Confirmed he's already in the system under that name, currently archived."

This is a **triple hallucination**: (1) No tool call was made to check the system, (2) Archived leads are excluded from the system prompt context, (3) There is no `search_lead` or `find_lead` tool.

## Full Trace

```
Voice note → agent_chat → LLM proposes lead, asks "Shall I create?"
    ↓
User text correction → _handle_owner_coach_whatsapp → agent_chat
    ↓
agent_chat loads history (system prompt with lead list, voice proposal, LLM's previous proposal)
    ↓
LLM called with: user_msg = "Yes. All good except... no space... It's Sahibjeet"
    ↓
LLM response (no data_keywords in msg, so enforcer does NOT fire):
    "Noted, Greg. Corrected — Sahibjeet Singh, no space. 
     Confirmed he's already in the system under that name, currently archived."
    ↓
Phantom update detector: "corrected" + "name" are ~59 chars apart — beyond the 30-char window → NO MATCH
    ↓
No phantom-lookup detector existed → "already in the system, archived" passes through
    ↓
No tool calls in response → falls through confirmation check → response sent verbatim to user
```

## Why Each Protection Layer Missed It

| Layer | Why it failed |
|-------|--------------|
| Enforcer | User message has no data keywords ("except" ≠ "correct"). enforcer_condition = False. |
| Phantom update regex | "corrected" at pos 13, "name" at pos 72. 59 chars > 30-char window. No match. |
| Phantom lookup regex | **Didn't exist** — only update claims were checked, not lookup claims. |
| System prompt | Told LLM not to invent search results but not "don't claim to have checked the system". |
| Tool schema | No `search_lead` or `find_lead` tool exists — LLM can't actually look up leads. |

## Fixes Applied (June 11, 2026)

### 1. Phantom-lookup detector (server.py, agent_chat block)

New regex that catches lookup-style hallucinations before they reach the user:

```python
_lookup_claim_re = re.compile(
    r"(?i)(?:already\s+(?:in|exists?)|found\s+(?:in|the)|checked\s+(?:the|in)|"
    r"currently\s+archived|archived\s+in|looked\s+up|searched\s+(?:the|for)|"
    r"in\s+the\s+system|under\s+that\s+name)"
)
```

When detected, re-calls the LLM with a fix prompt that explicitly states:
- "DO NOT claim to have checked the system or found a lead — you CANNOT look up leads."
- "If the user corrected a name/email/phone, acknowledge the correction and re-propose or generate the correct [TOOL_CALL:] block."

### 2. System prompt guardrail

Added a `CRITICAL` instruction to the agent system prompt:
> "Never claim to have 'checked the system' or 'found a lead in the system' without a [TOOL_CALL:] block. There is no search_lead tool that can find leads by name. The lead list in your context is a static snapshot — you CANNOT look up archived leads or 'check if a lead already exists.'"

### 3. Test coverage (6 new tests in test_enforcer.py)

- `TestPhantomLookup` — documents that lookup-type hallucinations are now caught
- `TestPhantomWindowBug` — tests the 30-char window edge case for update claims
- `TestNamingCorrectionOnProposal` — confirms enforcer doesn't fire on corrections

## How to Diagnose in the Future

1. **Check the LLM response** in the agent_chat_messages table:
   ```sql
   SELECT content FROM agent_chat_messages
   WHERE thread_id = (SELECT id FROM chat_threads
                      WHERE tenant_id = 'TENANT_ID' AND thread_type = 'coaching'
                      ORDER BY updated_at DESC LIMIT 1)
   ORDER BY created_at DESC LIMIT 3;
   ```
2. **Search for lookup phrases**: "already in the system", "currently archived", "found in the system", "checked the system"
3. **Verify no tool call was made**: Check if the response contains `[TOOL_CALL:`
4. **Check the system prompt context**: Archived leads are filtered with `stage != 'archived'` — the LLM can never "see" archived leads
5. **Check the enforcer log**: `ENFORCER FIRED` or `ENFORCER SKIPPED` in server logs
6. **Check the phantom detector logs**: `Phantom update corrected` or `Phantom lookup corrected`

## Related

- `ara-agent-chat-debugging` SKILL.md > "Bug: Phantom Detector Rewrites Text But Doesn't Execute (agent_chat Variant)"
- `test-driven-development` references > "Phantom-Update Detection" section
- Commit: `7d4979e`
