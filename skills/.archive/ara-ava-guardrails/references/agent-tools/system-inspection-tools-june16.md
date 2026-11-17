# System Inspection Tools — June 16, 2026

Four new read-only tools added to Ava's arsenal. They give her the ability to inspect system state, diagnose failures, and gather data for strategic analysis — without the ability to write code or modify the system.

## Tool 1: read_system_logs

**Purpose:** Read server logs with time range and text search. More powerful than `read_logs` (which only reads a small in-memory ring buffer).

**Schema:**
```python
"read_system_logs": {
    "description": "-- Read server logs with time range and text search. More powerful than read_logs (which uses a small ring buffer). Use to investigate failures. Args: {\"minutes\": 10, \"search\": \"attachment\", \"limit\": 20}",
    "read_only": True
}
```

**Handler (server.py ~line 4978):**
```python
import subprocess
cmd = ["journalctl", "-u", "ara-server", "--since", f"{minutes}min ago", "--no-pager", "-n", str(limit * 5)]
result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
lines = result.stdout.split("\n")
if search:
    lines = [l for l in lines if search.lower() in l.lower()]
output = "\n".join(lines[-limit:])
```

**Safety:** Subprocess runs journalctl — journalctl is strictly read-only. Timeout capped at 10 seconds. Result limited to `limit` lines.

**Use case:** "Why did the email send without an attachment?" → reads logs for `attachment` keyword in last 5 minutes.

## Tool 2: query_database

**Purpose:** Run read-only SQL queries against the ARA database for state inspection.

**Schema:**
```python
"query_database": {
    "description": "-- Query the ARA database directly (read-only SELECT only). Use to check state that tools don't expose. Allowed tables: action_items, scheduled_actions, leads, deals, documents, skills, conversations, agent_chat_messages. Args: {\"sql\": \"SELECT ... FROM ... WHERE ...\"}",
    "read_only": True
}
```

**Safety — `_validate_sql_query` function:**
- Rejects non-SELECT queries (DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, TRUNCATE, REPLACE, EXEC, EXECUTE, ATTACH, DETACH)
- Table whitelist: `action_items`, `scheduled_actions`, `leads`, `deals`, `documents`, `skills`, `conversations`, `agent_chat_messages`, `learning_notifications`, `integration_configs`, `induction_documents`, `cadence_configs`
- Sensitive column pattern block: `password`, `token`, `secret`, `key`, `config`, `credentials`, `api_key`
- Extracts table names from FROM/JOIN clauses using regex: `\b(?:FROM|JOIN)\s+(\w+)`
- Result limited to 50 rows, 5000 chars

**Use case:** "How many leads are in each stage?" → `SELECT stage, COUNT(*) FROM leads WHERE tenant_id='...' GROUP BY stage`

## Tool 3: read_code

**Purpose:** Read code from the ARA codebase to understand behavior for diagnosis.

**Schema:**
```python
"read_code": {
    "description": "-- Read code from the ARA codebase. Use to understand how a feature works before diagnosing. Args: {\"file\": \"server.py\", \"start_line\": 100, \"lines\": 30}",
    "read_only": True
}
```

**Safety — path traversal protection:**
```python
safe_path = os.path.realpath(os.path.join("/opt/ara", filename.lstrip("/")))
if not safe_path.startswith("/opt/ara/"):
    return f"Access denied: {filename} is outside /opt/ara/"
```

The `os.path.realpath()` call is critical — it resolves `../` before checking the prefix. Without it, `../../etc/passwd` would start with `/opt/ara/` before resolution and pass the check. This was the initial implementation bug fixed in commit `6990cb9`.

**Use case:** "How does the email dispatch handle attachments?" → reads email_utils.py or server.py email section.

## Tool 4: diagnose_failure

**Purpose:** Structured diagnosis of a failed action — combines logs, DB state, and file system checks.

**Schema:**
```python
"diagnose_failure": {
    "description": "-- Diagnose why a tool or action failed. Investigates logs, DB state, and file system to find root cause. Use when user asks 'what happened?', 'why did X fail?', or after a tool returns an error. Args: {\"action_id\": \"...\"} or {\"tool_name\": \"...\", \"error\": \"...\"}",
    "read_only": True
}
```

**Handler logic:**
1. Reads journalctl last 15 minutes, filters for ERROR/WARNING/Traceback or matching action_id prefix
2. If action_id provided, queries ActionItem (status, execution_state, outcome_state) and ScheduledAction (status, last_error, scheduled_at)
3. Returns structured DIAGNOSIS block with all findings concatenated

**Use case:** After `send_email` claims success but attachment is missing → `diagnose_failure(action_id="de57bd39")` → finds `"Attachment file not found: /opt/ara/uploads/..."` in logs.

## System Prompt Integration

A new `## System Inspection & Problem-Solving` section was added to `AGENT_SYSTEM_PROMPT_BASE` (after Rule #9, before Execution Intent Protocol). Key directives:

- **When to use:** Diagnostic questions, tool errors, state verification, system behavior questions
- **How to investigate:** Start with logs → DB → code. 2-3 inspection calls allowed. Report what you FOUND, not what you TRIED.
- **Communication pattern:** "Let me check the logs..." → "Found something..." → "Here's what I think happened..."
- **Diagnosis guidelines:** Cross-reference, never claim certainty, end with next action. Escalate to Johnny after 3 inspections.

## Tool Count

After adding these 4 tools: 57 total tools in `build_tools_schema()`.
