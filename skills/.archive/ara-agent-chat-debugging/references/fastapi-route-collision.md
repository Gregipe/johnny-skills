# FastAPI Route Collision — Same Path Pattern, Different Parameter Names

FastAPI matches routes by literal path **first**, then by parameterized path in **definition order**. If two routes share the same pattern but different parameter names, only the first one ever matches.

## Symptom

The frontend calls `GET /api/actions/aa001774` expecting a single ActionItem. The response is `{"actions": []}` — an empty list, not an error. No crash, no 404, just wrong data.

## Root Cause

```python
# Defined FIRST — matches /api/actions/{anything} as a lead_id
@app.get("/api/actions/{lead_id}")
def get_lead_actions(lead_id: str, db: ...):
    return {"actions": [...]}  # queries ActionItem WHERE ref_id == lead_id

# Defined LATER — NEVER REACHED because {lead_id} matches "aa001774" first
@app.get("/api/actions/{action_id}")
def get_action(action_id: str, db: ...):
    return {"id": ..., "title": ...}
```

FastAPI: `{lead_id}` and `{action_id}` are both `str` placeholders on the same path. The framework can't distinguish them — first one wins.

## Fix

Give one of them a distinct path prefix:

```python
# ✅ Distinct paths — no ambiguity
@app.get("/api/leads/{lead_id}/actions")       # lead-scoped
@app.get("/api/actions/{action_id}")            # single action by ID
```

Or use query parameters:
```python
@app.get("/api/actions")                        # /api/actions?action_id=XYZ
def get_action(action_id: str, db: ...):
```

## Detection

```bash
# Find all route definitions on the same path prefix
grep -n '@app\.\(get\|post\|patch\|delete\)("/api/actions/' server.py
```

Any path that appears with different parameter names but identical structure is a collision risk. Move one to a sub-path or query param.
