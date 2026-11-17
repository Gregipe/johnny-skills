# query_database Tool: SQLAlchemy text() Wrapping

**Symptom**: Ava calls `query_database` with a valid SQL query (e.g., `SELECT * FROM scheduled_actions WHERE tenant_id='...'`). The validation passes. But the tool returns:

```
Query error: Textual SQL expression 'SELECT * FROM scheduled_a...' should be explicitly declared as text('SELECT * FROM scheduled_a...')
```

All DIAGNOSTIC queries that use `query_database` silently fail.

**Root cause**: SQLAlchemy 2.x+ requires raw SQL strings to be wrapped in `text()` when passed to `db.execute()`:

```python
# ❌ BROKEN — SQLAlchemy 2.x rejects raw strings
db.execute("SELECT * FROM scheduled_actions WHERE ...")

# ✅ CORRECT
from sqlalchemy import text
db.execute(text("SELECT * FROM scheduled_actions WHERE ..."))
```

The `_validate_sql_query()` function passes the query through successfully (it validates the SQL string), but the actual execution at the `execute_tool` handler fails because the string isn't wrapped.

**Detection**: When testing DIAGNOSTIC queries, check `tool_results` for `query_database` entries:
```python
for t in tools:
    if t.get("tool") == "query_database":
        print(t.get("summary", ""))
```
If summary starts with "Query error: Textual SQL expression", this bug is present.

**Fix**: In the `query_database` handler within `execute_tool`, wrap the validated SQL:
```python
elif tool_name == "query_database":
    from sqlalchemy import text as _text
    sql = args.get("sql", "")
    valid, msg = _validate_sql_query(sql)
    if not valid:
        return f"Query rejected: {msg}"
    result = db.execute(_text(sql))
    ...
```

**Why this appears in DIAGNOSTIC queries specifically**: 
- CHITCHAT/CAPABILITY: never calls `query_database`
- SIMPLE_QUESTION: uses `get_action_items`, `get_pipeline_summary` — higher-level tools
- ACTION: uses `create_lead`, `send_email` — write tools
- STRATEGIC: uses `query_leads` (a higher-level wrapper that may or may not use raw SQL)
- DIAGNOSTIC: the ONLY mode that heavily uses `query_database` — so the bug only surfaces here
