# New Confirmation Flow Triggers (2026-06-29)

Additional trigger patterns for the ara-agent-chat-debugging umbrella that
post-date the current SKILL.md trigger section. Add these to the SKILL.md
trigger section when the file is split to go under 100KB.

| User Report | Root Cause | Reference |
|-------------|-----------|-----------|
| "I said yes and she asked me again" | PENDING_TTL expired OR clarification gate too strict | Pitfalls #6, #29 |
| "She output raw tool names (save_memory)" | _build_pending_description missing tool case | Pitfall #26 |
| "She said 3 steps but only did 2" | LLM text describes N steps but creates < N tool calls | Pitfalls #17, #30 |
| "I forwarded her message back and she cancelled" | Echo messages classified as confirm/reject | Pitfall #28 |
| "She claims WhatsApp sent but nothing arrived" | Sidecar false-positive on dead session | Pitfall #27 |
| "yes - run all three" was ignored | Variant confirmation bypassed clarification gate | Pitfall #29 |
| "She dropped Sai Bharat from the re-proposal" | LLM entity dropping on re-generation | Pitfall #30 |
| "Only confirmation flow has health check" | send_message_sync is the single choke point, not covered | Pitfall #31 |

## Quick Diagnostic Commands

```bash
# Check confirmation flow logs
journalctl -u ara-server --since "10m ago" | grep CONFIRM-FLOW

# Check for stale awaiting_approval pendings
python3 -c "
import sqlite3; db=sqlite3.connect('/opt/ara/ara.db')
rows = db.execute('''SELECT id, created_at, substr(title,1,80), execution_state
    FROM action_items WHERE tenant_id='3e736242'
    AND execution_state='awaiting_approval'
    ORDER BY created_at DESC LIMIT 10''').fetchall()
for r in rows: print(f'{r[0][:8]} | {r[1][:19]} | {r[3]:20s} | {r[2]}')
"

# Check for echo patterns in agent_chat_messages
python3 -c "
import sqlite3; db=sqlite3.connect('/opt/ara/ara.db')
rows = db.execute('''SELECT id, substr(content,1,100), created_at
    FROM agent_chat_messages WHERE tenant_id='3e736242'
    AND role='user' AND content LIKE '\u2728%'
    ORDER BY created_at DESC LIMIT 10''').fetchall()
for r in rows: print(f'{r[0][:8]} | {r[2][:19]} | {r[1]}')
"

# Check sidecar health (zombie detection)
curl -s http://localhost:8767/status | python3 -c "
import sys,json; d=json.load(sys.stdin)
print(f'connected={d.get(\"connected\")} | state={d.get(\"state\")} | decrypt_errors={d.get(\"decrypt_error_count\",0)} | healthy={d.get(\"healthy\",\"N/A\")}')
"
```

## Pending Fixes (from build plan — not yet implemented)

| # | Issue | Fix Location | Priority |
|---|-------|-------------|----------|
| 2 | Echo detection | server.py ~355, ~7009 | High |
| 3 | Variant confirmation gate | server.py ~7142 | High |
| 1 | Step-count mismatch check | server.py ~6493, ~6520 | Medium |
| 5 | Generic tool description | server.py ~6790 | Low |
| 4 | Entity injection guard | server.py ~7136, ~6134 | Low |
| 6 | Sidecar health in send_message_sync | whatsapp_sidecar_client.py, index.js | Critical |
