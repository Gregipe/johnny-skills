# Debugging ARA Tool Call Execution Failures

When Ava reports "system error" or tool calls silently fail, follow this diagnostic chain.

## 1. Check Cadence Configs

The most common cause of `trigger_cadence` failures is a misconfigured cadence template.

```bash
cd /Users/greg/ara
sqlite3 ara.db "SELECT template_id, json_extract(config, '$.steps') FROM cadence_configs"
```

**Check for:**
- **Empty steps** (`null` or `[]`) — the cadence has no sequence to schedule
- **Null delay_hours** — steps exist but `delay_hours` is null, causing the template.get("steps") lookup to work but scheduling to produce weird timing
- **Missing template_id** — the lead's `cadence_type` doesn't match any `CadenceConfig` row

**Fix empty steps** (add a WhatsApp → Email → Call sequence):

```python
cfg = json.loads(json.dumps(config.config))  # deep-copy to break SQLAlchemy ref tracking
cfg['steps'] = [
    {'channel': 'whatsapp', 'delay_hours': 0, 'desc': '...', 'repeat_count': 1, 'interval_hours': 0},
    {'channel': 'email', 'delay_hours': 48, 'desc': '...', 'repeat_count': 1, 'interval_hours': 0},
    {'channel': 'call', 'delay_hours': 144, 'desc': '...', 'repeat_count': 1, 'interval_hours': 0},
]
config.config = dict(cfg)  # assign fresh dict so SQLAlchemy detects mutation
db.commit()
```

**Fix null delay_hours:**

```python
for step in cfg.get('steps', []):
    if step.get('delay_hours') is None: step['delay_hours'] = 0
    if step.get('repeat_count') is None: step['repeat_count'] = 1
config.config = dict(cfg)
db.commit()
```

## 2. SQLAlchemy JSON Column Mutation Bug

The `CadenceConfig.config` column uses `Column(JSON)` without `MutableDict.as_mutable(JSON)`. SQLAlchemy does NOT detect in-place mutations of nested dicts.

**❌ This does NOT persist:**
```python
cfg = config.config
cfg['steps'] = [...]        # mutates in-place
config.config = cfg          # same object reference — SQLAlchemy skips it
db.commit()                  # silently does nothing
```

**✅ This DOES persist:**
```python
cfg = json.loads(json.dumps(config.config))  # fresh copy
cfg['steps'] = [...]
config.config = dict(cfg)    # new dict object → SQLAlchemy detects change
db.commit()
```

Or alternatively, serialize to string so SQLAlchemy definitely sees the difference (but then the column returns strings, not dicts — see safety fix below):

```python
config.config = json.dumps(cfg)  # always detected as changed
db.commit()
```

## 3. String Config Safety in _schedule_cadence_for_lead

If config was stored as a JSON string (e.g., from fix step 2 above), `template.get("steps", [])` throws `AttributeError: 'str' object has no attribute 'get'`.

The fix is a safety check in `_schedule_cadence_for_lead`:

```python
if isinstance(template, str):
    try:
        template = json.loads(template)
    except (json.JSONDecodeError, TypeError):
        return {"scheduled": 0, "reason": f"invalid json for {cadence_type}"}
```

Add this right after the `template = configs.get(cadence_type)` lookup.

## 4. Misleading "Success" Message in Tool Execution

When one tool fails, the follow-up LLM prompt still says "All requested actions have been completed successfully:", which causes Ava to misreport the error.

**Fix in server.py (~line 4028):** Check if any result starts with "Error" and use "Some actions encountered errors:" instead. Add an `errors` accumulator:

```python
results = []
errors = []
for tool_name, args in tool_calls:
    result = execute_tool(tool_name, args, db, wa, tenant_id)
    results.append(f"Tool '{tool_name}': {result}")
    if result.startswith("Error"):
        errors.append(result)

if errors:
    follow_up = f"Some actions encountered errors:\n{result_summary}\n\n..."
else:
    follow_up = f"All requested actions have been completed successfully:\n{result_summary}\n\n..."
```

## 5. Verifying a Lead's Cadence State

Quick check from terminal:

```bash
cd /Users/greg/ara
python3 -c "
import sys, json; sys.path.insert(0, '.')
from database import init_db, Lead, ScheduledAction, CadenceConfig
db = init_db()
lead = db.query(Lead).filter(Lead.name == 'Gregory Ipe').first()
print(f'Stage: {lead.stage}, Cadence: {lead.cadence_type}')
pending = db.query(ScheduledAction).filter(ScheduledAction.lead_id == lead.id, ScheduledAction.status.in_([\"pending\", \"firing\"])).all()
print(f'Pending actions: {len(pending)}')
config = db.query(CadenceConfig).filter(CadenceConfig.template_id == lead.cadence_type).first()
steps = config.config.get('steps', []) if config else []
print(f'Config steps: {len(steps)}')
db.close()
"
```

## 6. Chat Persistence Verification

Chats persist via SQLite — `agent_chat_messages` + `chat_threads` tables. Verify:

```bash
sqlite3 /Users/greg/ara/ara.db "SELECT COUNT(*) FROM agent_chat_messages"
sqlite3 /Users/greg/ara/ara.db "SELECT COUNT(*) FROM chat_threads"
```

Frontend stores `activeThreadId` in `localStorage` (key `ara_active_thread`, 12-hour expiry) and falls back to loading the latest thread via `GET /api/threads/{tenant_id}` on page load. Survives server restarts as long as `ara.db` is on disk.

## 7. Tool Dispatch Flow Summary

For understanding where failures occur:

```
User sends message
  → POST /api/agent/chat/{tenant_id}
    → Build system prompt + conversation history from DB
    → call_llm() → Ava responds with [TOOL_CALL: {...}]
    → Parse [TOOL_CALL:] blocks via regex
    → For each tool: execute_tool(tool_name, args, db, wa, tenant_id)
    → execute_tool dispatches by tool_name:
        - "trigger_cadence" → _schedule_cadence_for_lead()
        - "send_whatsapp" → wa.send_message_sync()
        - "update_lead" → db update
        - etc.
    → Returns string result ("Cadence triggered..." or "Error: ...")
    → Build follow-up prompt with results → call_llm() for synthesis
    → Save user + assistant messages to DB
    → Return {"response": "...", "thread_id": "..."}
```
