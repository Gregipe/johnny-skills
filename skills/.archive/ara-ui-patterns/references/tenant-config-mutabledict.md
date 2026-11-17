# Tenant Config MutableDict Pitfall

## The Problem

`tenant.config` in the Tenants model uses `MutableDict.as_mutable(JSON)`:

```python
config = Column(MutableDict.as_mutable(JSON), default=dict)
```

Assignment via `t.config["key"] = val` or `t.config = new_dict` does NOT reliably persist to the database. The ORM's mutation tracking fails silently — the server returns 200 but the value is never saved.

## The Fix

Use raw SQL UPDATE for writes:

```python
from sqlalchemy import text
import json

existing = db.execute(text("SELECT config FROM tenants WHERE id=:id"), {"id": tenant_id}).scalar() or "{}"
cfg = json.loads(existing) if isinstance(existing, str) else (dict(existing) if existing else {})
cfg["key"] = value
db.execute(text("UPDATE tenants SET config=:cfg WHERE id=:id"), {"cfg": json.dumps(cfg), "id": tenant_id})
```

## Reads

Reading `t.config` works normally — the ORM deserializes the JSON on access. No SQL bypass needed for reads.

## Affected API Endpoints

- `PUT /api/tenants/{tenant_id}/settings` — updates `industry` in config
- `PUT /api/tenants/{tenant_id}/segments` — updates segment definitions

Any new endpoint that modifies tenant.config must use this pattern.
