# Tool-Coverage Audit — June 4, 2026

## Why This Was Needed

Ava's system prompt had 46 tools defined in `AGENT_TOOL_SCHEMA` (the final section of the prompt), but only ~14 had trigger conditions in the prompt body. The remaining 32 were "buried" — the LLM would only discover them by reading through the tool schema at the very end, and had no prompt-level trigger to associate them with specific user questions.

## The Audit Method

Don't audit by reading the prompt. Use code to extract and cross-reference:

```python
import re
with open('server.py') as f: source = f.read()

# Extract AGENT_SYSTEM_PROMPT_BASE
start = source.find('AGENT_SYSTEM_PROMPT_BASE = """')
qs = source.index('"""', start) + 3
qe = source.index('"""', qs)
base = source[qs:qe]

# Extract tool names from AGENT_TOOL_SCHEMA
schema_start = source.find('AGENT_TOOL_SCHEMA = """')
sql_qs = source.index('"""', schema_start) + 3
sql_qe = source.index('"""', sql_qs)
schema = source[sql_qs:sql_qe]
tools = re.findall(r'\*\*(\w+)\*\*', schema)

# Cross-reference each tool
for tool in tools:
    matches = list(re.finditer(re.escape(tool), base, re.IGNORECASE))
    if not matches: print(f"❌ {tool}")
    elif len(matches) <= 2: print(f"⚠️  {tool}")
    else: print(f"✅ {tool}")
```

## The Three Categories Found

### 1. ✅ Well-referenced (3+ mentions in prompt body)
send_whatsapp, web_search, read_logs

### 2. ⚠️ Minimally referenced (1-2 mentions)
send_whatsapp_to_owner, search_leads, get_conversation_history, get_activity_log, get_system_map, get_cadence_config, get_action_items, query_leads, list_documents, evaluate_qualification, mark_meeting_booked, debug_schedule, check_health, add_skill, search_knowledge_base

### 3. ❌ Only in AGENT_TOOL_SCHEMA — zero prompt body references
send_email, schedule_message, schedule_email, schedule_follow_up, cancel_scheduled, trigger_cadence, update_lead, update_lead_stage, update_deal, update_deal_stage, create_lead, create_deal, attach_to_deal, detach_from_deal, get_lead_detail, get_pipeline_summary, get_summary, search_deals, fetch_url, save_learning, send_internal_note, set_reminder, create_action_item, escalate_to_human, log_insight, upload_document, add_to_watchlist, resolve_watchlist_item

## The Fix Applied

Expanded System Awareness section from ~10 lines to ~25+ lines with explicit trigger conditions for every tool. Format:
```
- **tool_name** — trigger condition.
```

Example section snippet:
```
## System Awareness
- **Read-only tools** (call freely): web_search, fetch_url, search_leads, search_deals, search_knowledge_base, get_*, read_logs, debug_schedule, check_health, query_leads, list_documents.
- **get_summary** — when Greg asks "what happened today/recently"
- **get_pipeline_summary** — when Greg asks "what's the pipeline look like"
- **get_lead_detail** — when Greg asks about a specific lead's profile
- **create_lead** / **create_deal** — when Greg says "add a lead/deal"
- **update_lead** / **update_deal** — when Greg wants to change data
- **set_reminder** — when Greg asks to be reminded
- **trigger_cadence** — when Greg says "start outbound"
- **schedule_message** / **schedule_email** — when Greg wants to schedule
- ... (one line per tool)
```

## Key Lessons for Future Audits

1. **Over-trusting AGENT_TOOL_SCHEMA is dangerous** — The schema is at the very end of the prompt. LLMs give disproportionate weight to the beginning. Tools only in the schema are effectively buried.

2. **Wildcards (`get_*`) work for permissions but not triggers** — Telling Ava "get_* is call freely" doesn't tell her WHEN to call `get_summary` vs `get_lead_detail`. Each distinct tool needs its own trigger line.

3. **Pipeline inline context is the hallucination trap** — `INDUCTION: {skills_context}` makes the LLM think it already has the answer. Place the Tool-First Rule AFTER the Pipeline section so the LLM reads data, then reads "do NOT rely on inline data — call the tool."

4. **Two-step testing** — Test each fix: (a) verify no crash via endpoint, (b) verify behavior via response text AND server log count of LLM calls. One LLM call = no tool fired. Two LLM calls = tool executed + result synthesized.

5. **Stale .pyc** — After editing server.py, delete `__pycache__/server.cpython-*.pyc` AND kill all Python processes. A new process may load old bytecode.
