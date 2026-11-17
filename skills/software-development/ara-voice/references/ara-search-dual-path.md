# ARA Search: Dual Code-Path Bug

## The Pattern

ARA's `search_leads` (and `search_deals`) has **two separate implementations**
in server.py. A fix applied to one path does NOT propagate to the other.

### Path A: REST API endpoint
```
GET /api/leads/search?q=Ram+Gopal+Nanda
```
Defined as `def search_leads(q: str, db)`. Used by dashboard search, chat agent.

### Path B: Voice tool execution
```
POST /api/voice/tool {tool: "search_leads", args: {query: "Ram Gopal Nanda"}}
```
Defined inline inside `execute_tool()` under `elif tool_name == "search_leads":`.
Used by voice agent and WhatsApp agent.

## Space-Normalized Name Matching

Indian names frequently have space variants: "Ram Gopal" vs "Ramgopal",
"R K Sharma" vs "RK Sharma". SQLite `LIKE` treats spaces literally.

**Fix for Path A (REST endpoint):**
```python
q_like = f"%{q}%"
q_norm_like = f"%{q.replace(' ', '')}%"
leads = db.query(Lead).filter(
    Lead.tenant_id == tenant.id,
    Lead.stage != "archived",
    (Lead.name.ilike(q_like)) |
    (func.replace(Lead.name, " ", "").ilike(q_norm_like)) |
    (Lead.phone.ilike(q_like)) | ...
)
```

**Fix for Path B (voice tool exec):**
```python
query = args.get("query", "")
query_norm = query.replace(" ", "")
leads = db.query(Lead).filter(
    Lead.tenant_id == tenant_id,
    (Lead.name.ilike(f"%{query}%")) |
    (func.replace(Lead.name, " ", "").ilike(f"%{query_norm}%")) |
    (Lead.company.ilike(f"%{query}%")) |
    (func.replace(Lead.company, " ", "").ilike(f"%{query_norm}%")) |
    (Lead.phone.ilike(f"%{query}%")) | ...
)
```

## Verification

```bash
# REST API: curl "http://localhost:8766/api/leads/search?q=Ram+Gopal+Nanda"
# Voice tool: curl -X POST http://localhost:8766/api/voice/tool \
#   -H 'Content-Type: application/json' \
#   -d '{"secret":"...","tool":"search_leads","args":{"query":"Ram Gopal"},"tenant_id":"3e736242"}'
```

Both MUST return matching leads.

## `import func`

The `sqlalchemy.func` import must be at the top of server.py:
```python
from sqlalchemy import or_, func
```

Without it, `func.replace(...)` raises `NameError` at module load.

## Sibling Risk: search_deals, search_actions

Any search function with its own inline query in `execute_tool()` has the same
dual-path structure. Apply space normalization to all of them proactively.
