# API Key Management Architecture — June 2026

## Overview

Three-tier resolution chain for API keys in ARA: **tenant config → platform config → env var**.

```
resolve_api_key("tavily", tenant_id="3e736242")
    ├── 1. Tenant config → tenant.config.api_keys.tavily (BYOK)
    ├── 2. Platform config → platform_config table → tavily_api_key
    └── 3. Env var fallback → TAVILY_API_KEY (legacy)
```

## Database Layer

### PlatformConfig Table (`database.py`)

```sql
CREATE TABLE platform_config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    label       TEXT,
    updated_at  TIMESTAMP,
    created_at  TIMESTAMP
);
```

Tenant-level keys live in the existing `Tenant.config` JSON column under `api_keys`:
```json
{
    "name": "Hunar",
    "api_keys": {
        "tavily": null,
        "openai": "sk-..."
    }
}
```

## Resolution Function (`server.py`)

```python
def resolve_api_key(service: str, tenant_id: str = None) -> str:
    # 1. Tenant-specific
    if tenant_id:
        db = init_db()
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant and tenant.config:
            cfg = tenant.config if isinstance(tenant.config, dict) else {}
            tenant_key = cfg.get("api_keys", {}).get(service)
            if tenant_key:
                return tenant_key
        db.close()
    # 2. Platform-wide
    db = init_db()
    row = db.query(PlatformConfig).filter(PlatformConfig.key == f"{service}_api_key").first()
    if row:
        return row.value
    # 3. Env var fallback
    env_name = f"{service.upper()}_API_KEY"
    return os.environ.get(env_name, "")
```

## API Endpoints

### Platform-level (admin-managed)
| Endpoint | Description |
|----------|-------------|
| `GET /api/platform/api-keys` | List all keys (masked) |
| `PUT /api/platform/api-keys` | Set key: `{"service":"tavily","value":"sk-...","label":"Tavily Search"}` |
| `DELETE /api/platform/api-keys/{service}` | Remove a key |

### Tenant-level (BYOK — tenant brings own key)
| Endpoint | Description |
|----------|-------------|
| `GET /api/tenants/{tid}/api-keys` | List tenant keys (masked) |
| `PUT /api/tenants/{tid}/api-keys` | Set key: `{"service":"tavily","value":"sk-..."}` |
| `DELETE /api/tenants/{tid}/api-keys/{service}` | Remove tenant override |

## Frontend UI

The Settings page (`dashboard.js` → `renderSettings()`) has a **🔑 API Keys** section at the bottom with password fields. Tenants can enter their own keys there. Empty field = inherits from platform level.

## Security Notes (v1)

- v1 stores keys in plaintext in the DB (platform_config table and tenant config JSON)
- v1.5 should add `MASTER_ENCRYPTION_KEY` env var + Fernet symmetric encryption
- Platform keys are masked in API responses (`tvly****`)
- Tenant keys are also masked in the Settings UI

## Adding a New Service

To add a new resolvable API key (e.g., "openai"):
1. No code changes needed — the resolution function is service-agnostic
2. Set at platform level: `PUT /api/platform/api-keys {"service":"openai","value":"sk-..."}`
3. Code that needs it: `resolve_api_key("openai", tenant_id)`
