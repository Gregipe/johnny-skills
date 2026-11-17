# System Inspection Tools — June 2026

Four new read-only tools give Ava the ability to investigate system state:

## Tools

### read_system_logs
- Wraps `journalctl -u ara-server --since {minutes}min ago --no-pager -n {limit}`
- Supports text search (`search` param filters lines)
- Returns last `limit` lines (default 20)
- More powerful than `read_logs` (which uses a small in-memory ring buffer)

### query_database
- Read-only SELECT on whitelisted tables
- SQL injection hardened: blocks DROP/DELETE/UPDATE/INSERT/ALTER/CREATE/TRUNCATE/EXEC
- Whitelisted tables: action_items, scheduled_actions, leads, deals, documents, skills, conversations, agent_chat_messages, learning_notifications, integration_configs, induction_documents, cadence_configs
- Blocks sensitive column patterns: password, token, secret, key, config, credentials, api_key
- Returns results as JSON (max 5000 chars, max 50 rows)

### read_code
- Reads files from /opt/ara/ directory only
- Path traversal hardened: uses `os.path.realpath()` before checking prefix
- Supports line ranges (start_line, lines)
- Returns file snippet with line numbers

### diagnose_failure
- Structured diagnosis combining logs + DB state
- Checks journalctl for errors/warnings (last 15 min)
- If action_id provided, queries ActionItem + ScheduledAction state
- Returns formatted diagnosis with evidence

## Safety Architecture

```
_validate_sql_query(sql)
  ├── Must start with SELECT
  ├── Block dangerous keywords (DROP, DELETE, etc.)
  ├── Extract table names from FROM/JOIN → check whitelist
  └── Block sensitive column patterns

read_code file access
  └── os.path.realpath(join("/opt/ara", filename)) → must start with "/opt/ara/"
```

## Prompt Integration

Added "System Inspection & Problem-Solving" section to AGENT_SYSTEM_PROMPT_BASE (after Rule #9):
- When to use: user asks "why did X fail?", "what happened?", diagnostic questions
- How to iterate: 2-3 inspection calls, don't give up after one
- How to communicate: "Let me check..." → "Found..." → "Here's what I think happened..."
- Diagnosis guidelines: cross-reference logs+DB+code, never claim certainty

## Code Location

All handlers in `execute_tool()` at ~line 4978-5075 of server.py.
Validator at module level (~line 5090).
