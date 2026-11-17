# API Key Resolution — Session Implementation Reference

## Context
Built June 1, 2026. Root cause: Ava's web_search fell back to DuckDuckGo HTML scraping (HTTP 202 rate-limit) because no Tavily API key was configured. No key management system existed — keys were scattered as `os.environ.get()` calls at module level.

## Files Changed

### database.py
Added `PlatformConfig` model (platform-level config, no tenant_id).

### server.py
- Added `resolve_api_key(service, tenant_id=None)` function
- Removed module-level `TAVILY_API_KEY = os.environ.get(...)`
- Updated `_search_tavily()` to accept `api_key` parameter instead of using global
- Updated `web_search()` to accept `tenant_id` parameter, resolve key dynamically
- Wired `execute_tool()` → passes `tenant_id` to `web_search(query, tenant_id=tenant_id)`
- Added 6 REST endpoints for key CRUD (3 tenant-level, 3 platform-level)

### static/dashboard.js
- Updated `renderSettings()`: fetches API keys alongside settings, renders 🔑 API Keys section with password fields
- Updated `saveSettings()`: saves API keys via PUT/DELETE after regular settings

### dashboard_template.py
- Bumped cache-busting version: `dashboard.js?v=15` → `dashboard.js?v=16`

## Resolution Chain (in order)

```
tenant.config.api_keys.tavily         → highest priority (BYOK)
platform_config WHERE key='tavily_api_key'  → fallback (platform-level)
TAVILY_API_KEY env var                → last resort (legacy)
```

## How the Key Flows at Runtime

```
User asks → LLM selects web_search tool → execute_tool("web_search", args, db, wa, tenant_id)
    → web_search(query, tenant_id=tenant_id)
    → resolve_api_key("tavily", tenant_id)
    → tenant.config.api_keys? → platform_config table? → env var?
    → _search_tavily(query, max_results, api_key) [if key found]
    → _search_ddg(query, max_results) [fallback if no key or tavily failed]
```

## Current State (after June 1 session)
- **Platform key:** Set via `PUT /api/platform/api-keys` → `tvly-dev-4SyC…dZdb`
- **Tenant keys:** None set (tenant `3e736242` has no overrides)
- **Env var:** Unset
- **Resolution verified:** Falls through tenant (empty) → returns platform key
- **Settings UI:** 🔑 API Keys section visible in Settings tab
- **System prompt guard:** Prevents non-business searches (from previous session)

## API Endpoints Added

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/platform/api-keys` | List platform keys (masked: `tvly****`) |
| `PUT` | `/api/platform/api-keys` | Set key: `{"service":"tavily","value":"..."}` |
| `DELETE` | `/api/platform/api-keys/{service}` | Remove a platform key |
| `GET` | `/api/tenants/{tid}/api-keys` | List tenant keys (masked) |
| `PUT` | `/api/tenants/{tid}/api-keys` | Set tenant key (BYOK) |
| `DELETE` | `/api/tenants/{tid}/api-keys/{service}` | Remove tenant key → falls through to platform |

## Next Steps (v1.5)
- Add `MASTER_ENCRYPTION_KEY` env var
- Encrypt all stored keys using `cryptography.fernet` before DB write
- Decrypt on read in `resolve_api_key()`
- Support more services (openai, serpapi, etc.) as needed
