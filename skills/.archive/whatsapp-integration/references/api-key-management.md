# API Key Management Architecture (ARA Server)

## Resolution Chain

Every API key resolves through a three-tier hierarchy at runtime:

```
tenant.config.api_keys.{service}  ──┐
                                     ├──→ highest priority (BYOK)
platform_config table (value)       ──┤
                                     ├──→ fallback (operator-managed)
os.environ["{SERVICE}_API_KEY"]     ──┘
                                     └──→ last resort (legacy)
```

### Implementation

```python
def resolve_api_key(service: str, tenant_id: str = None) -> str:
    """Resolve an API key: tenant → platform → env var."""
    from database import Tenant, PlatformConfig
    
    db = init_db()
    try:
        # 1. Tenant-specific override
        if tenant_id:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if tenant and tenant.config:
                tenant_keys = tenant.config.get("api_keys", {}) if isinstance(tenant.config, dict) else {}
                if service in tenant_keys and tenant_keys[service]:
                    return tenant_keys[service]
        
        # 2. Platform-wide config
        pc = db.query(PlatformConfig).filter(PlatformConfig.key == f"{service}_api_key").first()
        if pc and pc.value:
            return pc.value
        
        # 3. Env var fallback (legacy)
        env_name = f"{service.upper()}_API_KEY"
        return os.environ.get(env_name, "")
    finally:
        db.close()
```

### Where called

- `web_search(query, max_results, tenant_id)` — resolves "tavily" key
- Future: any service integration that needs tenant-provided or platform-wide credentials

## Storage

### Platform Table (`platform_config`)

```sql
CREATE TABLE platform_config (
    key TEXT PRIMARY KEY,         -- e.g. "tavily_api_key"
    value TEXT NOT NULL,          -- plaintext in v1, encrypted in v2
    label TEXT,                   -- human-readable ("Tavily Search API")
    updated_at TIMESTAMP,
    created_at TIMESTAMP
);
```

Set platform keys via:
```
PUT /api/platform/api-keys
{"service": "tavily", "value": "sk-...", "label": "Tavily Search API"}

GET /api/platform/api-keys  →  {"keys": {"tavily": "tvly****"}, "services": ["tavily"]}
DELETE /api/platform/api-keys/{service}
```

### Tenant Config (`tenants.config` JSON field)

Tenants can BYOK via the `api_keys` sub-key in their config JSON:

```json
{
  "name": "Tenant Name",
  "agent_name": "Ava",
  "owner_name": "Owner",
  "api_keys": {
    "tavily": "tvly-tenant-specific-key"
  }
}
```

Set tenant keys via:
```
PUT /api/tenants/{tenant_id}/api-keys
{"service": "tavily", "value": "sk-..."}

GET /api/tenants/{tenant_id}/api-keys
DELETE /api/tenants/{tenant_id}/api-keys/{service}
```

### Settings UI

Both platform and tenant keys are manageable from the dashboard:
- **Settings page** → scroll to bottom → **🔑 API Keys** section (password field, masked)
- Leave blank → inherits platform key
- Fill in → overrides for that tenant

## Pitfalls

- **`resp.json()` on urllib responses (CRITICAL)**: `urllib.request.urlopen()` returns an `http.client.HTTPResponse` object which does NOT have a `.json()` method. Use `import json; json.loads(resp.read())` instead. The error `'HTTPResponse' object has no attribute 'json'` is silently swallowed by blanket `except Exception` handlers — the Tavily search function falls through to DuckDuckGo, which then gets rate-limited. The user sees "Search failed (Tavily and DuckDuckGo both unavailable)" and has no idea the key was correct and working.

- **PlatformConfig key naming convention**: Keys in the `platform_config` table use `"{service}_api_key"` format (e.g., `tavily_api_key`). The API endpoints use the short service name `"tavily"` and expand it to `"tavily_api_key"` for storage. Keep this consistent across all new services.

- **No encryption in v1**: Keys stored in plaintext in both the `platform_config` table and `tenants.config` JSON column. Add `MASTER_ENCRYPTION_KEY` env var + Fernet encryption when ready for v2.

- **Tenant config JSON type**: The `tenants.config` column is SQLAlchemy `JSON`, which can return either a `dict` or a string depending on the SQLite JSON adapter. Always check `isinstance(tenant.config, dict)` before accessing `.get("api_keys", {})`.

- **Settings page API keys section**: Added as a 4th section in `renderSettings()` (dashboard.js line ~3915). Uses `GET /api/tenants/{TENANT}/api-keys` to load masked values, `PUT` to save. The Tavily field has id `sKeyTavily`.
