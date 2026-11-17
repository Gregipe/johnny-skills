---
name: ara-tenant-specific-infrastructure
category: software-development
description: Patterns for building tenant-configurable infrastructure in ARA — every new feature must be keyed by tenant_id and derive behavior from tenant.config. Covers the principle, segments API pattern, lead auto-assignment, skill filtering from tenant config, and the design rule for all new features.
---

# ARA Tenant-Specific Infrastructure

**Core principle (from Greg, May 2026):** "Is this Hunar-specific or should it work for any tenant?" If the answer is "any tenant," the config/storage/API MUST be keyed by `tenant_id` and the behavior MUST derive from `tenant.config`. No hardcoded company names, no assumptions about what segments or industries a tenant serves.

## When to Use

- Building any new ARA feature, endpoint, or model
- Adding a per-tenant configuration option
- Creating a new API endpoint — always check if it needs `{tenant_id}` in the path
- Modifying `load_skills_for_prompt()` or any skill-filtering logic
- Adding lead creation or auto-tagging logic

## Architecture Pattern

### Storage: Two-Layer Model

ARA uses a **two-layer storage model** for tenant configuration. The guiding question: *Will you ever need to query, sort, authenticate, or RBAC-filter by this field?*

#### Layer 1 — Dedicated Tables (Queryable Data)

If you'd ever write `WHERE field = x` or `ORDER BY field`, it belongs in a dedicated table:

```python
class Agent(Base):
    __tablename__ = "agents"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, unique=True)
    agent_name = Column(String, nullable=False, default="Ava")
    personality_tone = Column(String, default="chirpy_uplifting_witty")
    avatar = Column(String, default="")

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    role = Column(String, default="admin")  # admin, agent, viewer
    status = Column(String, default="active")
```

**What goes in dedicated tables:**

| Data | Why table? |
|------|-----------|
| `agent_name` | Need to query "what tenants have agent named Meera?" |
| `owner_name` | Need to authenticate/administer users |
| User roles | RBAC filtering ("show only leads assigned to this user") |
| User email/phone | Communication, auth, uniqueness constraints |

#### Layer 2 — `tenant.config` JSON Column (Non-Queryable Blob)

All per-tenant configuration that is **read at prompt-build time and never queried** lives in the `tenants` table's `config` JSON column:

```python
class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(String, primary_key=True)
    config = Column(JSON, default=dict)  # Non-queryable per-tenant settings
```

**What goes in config JSON:**

| Data | Why JSON? |
|------|-----------|
| Segment definitions | Complex nested structure, read-once at prompt time |
| Brand voice / personality | Never queried, only rendered |
| ICP / ideal customer profile | Read-only at prompt build |
| Induction Q&A | Structured but only used for context |
| Integration settings | Variable per integration type |

**CAUTION:** `MutableDict`/`MutableList` (used by `JSON` columns) do NOT support Python truthiness checks (`if not t.config`), direct `__setitem__` after assignment, or reassignment the way regular dicts do. Use `sqlalchemy.text("UPDATE tenants SET config=...")` with JSON serialization for writes (see Pitfalls).

### Access Pattern: `_get_agent_context()` Helper

A single helper reads from both layers and returns a consistent dict:

```python
def _get_agent_context(tenant_id, db):
    from database import Agent, User, Tenant
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    company = tenant.name if tenant else "your company"
    agent = db.query(Agent).filter(Agent.tenant_id == tenant_id).first()
    agent_name = agent.agent_name if agent else "Ava"
    admin = db.query(User).filter(User.tenant_id == tenant_id, User.role == "admin").first()
    owner_name = admin.name if admin else "Admin"
    return {"agent_name": agent_name, "owner_name": owner_name, "company": company}
```

**Used at every prompt-build site.** Never hardcode names in prompts.

### Settings API: Single Source of Truth

```python
@app.get("/api/tenants/{tenant_id}/settings")
def get_tenant_settings(tenant_id, db):
    ctx = _get_agent_context(tenant_id, db)
    agent = db.query(Agent).filter(Agent.tenant_id == tenant_id).first()
    return {
        "tenant": {"id": t.id, "name": t.name, "config": t.config or {}},
        "agent": {"name": ctx["agent_name"], "personality_tone": agent.personality_tone},
        "admin": {"name": ctx["owner_name"], "email": admin.email if admin else ""},
        "industry": t.config.get("industry", "") if t.config else "",
    }

@app.put("/api/tenants/{tenant_id}/settings")
def update_tenant_settings(tenant_id, data, db):
    # Updates agents table, users table, tenants.name, AND tenant.config
    # based on which keys are present: agent_name, owner_name, company, industry
```

The Settings tab in the sidebar reads/writes through this single endpoint. It cross-cuts Agent table, User table, Tenant.name, and tenant.config atomically.

## Induction Setup Flow (Future)

When building the induction wizard for new tenants, the flow is:

```
Step 1: "What should I call your AI agent?"  →  agents.agent_name
Step 2: "What should the agent call you?"    →  users.name (role=admin)
Step 3: "What's your company called?"        →  tenants.name
Step 4: "What industry / use case?"          →  tenant.config.industry
         ↓
Induction begins (learn proposition, ICP, segments)
```

The wizard writes to three tables. After setup, all settings are editable via the Settings page.

### API: Always `{tenant_id}` in Path

Every tenant-specific endpoint includes `{tenant_id}` in the URL path:

```python
@app.get("/api/tenants/{tenant_id}/segments")
@app.put("/api/tenants/{tenant_id}/segments")
@app.post("/api/tenants/{tenant_id}/segments/reassign")
@app.get("/api/tenants/{tenant_id}/leads")
@app.post("/api/tenants/{tenant_id}/leads")
@app.post("/api/induction/{tenant_id}/upload")
```

### DB: Every Model Has `tenant_id`

Every data model that is per-tenant MUST have a `tenant_id` foreign key:

```python
class Skill(Base):
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
class Lead(Base):
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
class Conversation(Base):
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
```

All queries filter by tenant_id:
```python
skills = db.query(Skill).filter(Skill.tenant_id == tenant_id).all()
```

## Segment Config (Reference Implementation)

### Config Structure

```json
{
  "segments": {
    "logistics": {
      "keywords": ["logistics", "delivery", "fleet", "warehouse"],
      "company_patterns": ["delhivery", "dhl", "fedex"],
      "description": "Logistics and supply chain companies"
    },
    "bfsi": {
      "keywords": ["bfsi", "bank", "finance", "insurance", "compliance"],
      "company_patterns": ["bajaj", "kotak", "hdfc"],
      "description": "Banking and financial services"
    }
  }
}
```

> **WARNING:** The examples above are from one tenant's config. They are NOT defaults. A new tenant (e.g., US staffing) defines their own segments. The code must handle an empty segments config gracefully — showing all skills unfiltered.

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/tenants/{tenant_id}/segments` | Read segment config |
| `PUT` | `/api/tenants/{tenant_id}/segments` | Update all segments (full replace) |
| `POST` | `/api/tenants/{tenant_id}/segments/reassign` | Re-run auto-assignment for all leads |

### Lead Auto-Assignment

`auto_assign_segment(lead, db)` is called on lead creation:

```python
def auto_assign_segment(lead, db):
    from database import Tenant
    if not lead or not lead.company:
        return
    current_segment = lead.segment or ""
    if current_segment:
        return  # Already has a segment
    tenant = db.query(Tenant).filter(Tenant.id == lead.tenant_id).first()
    if not tenant:
        return
    segments_config = (tenant.config or {}).get("segments", {})
    if not segments_config:
        return
    company_lower = lead.company.lower()
    for seg_name, seg_data in segments_config.items():
        for pattern in seg_data.get("company_patterns", []):
            if pattern.lower() in company_lower:
                lead.segment = seg_name
                return
```

**Wired at:** `create_lead()` endpoint (after cadence assignment). Also available via `POST /api/tenants/{tenant_id}/segments/reassign`.

### Skill Filtering from Config

`load_skills_for_prompt()` reads segment keywords from tenant config, not hardcoded Python:

```python
tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
segments_config = (tenant.config or {}).get("segments", {}) if tenant else {}
segment_keywords = {}
all_segment_keywords = []
for seg_name, seg_data in segments_config.items():
    seg_keywords = seg_data.get("keywords", []) + seg_data.get("company_patterns", [])
    segment_keywords[seg_name] = seg_keywords
    all_segment_keywords.extend(seg_keywords)

def is_relevant_for_segment(skill, seg):
    if not seg:
        return True
    text = (skill.key + " " + skill.value).lower()
    keywords = segment_keywords.get(seg, [])
    if not all_segment_keywords:
        return True  # No segment config, show everything
    mentions_any_segment = any(kw in text for kw in all_segment_keywords)
    if not mentions_any_segment:
        return True  # General skill, show to everyone
    return any(kw in text for kw in keywords)
```

**Filtering:** general skills (no segment keyword) → shown to ALL; segment-specific → matching leads only; skills mentioning other segments → hidden.

## Tenant Relevance Filtering (Search Lens)

**Problem:** Generic web searches for company news (e.g. "latest news HDFC Bank") return consumer noise — credit card changes, FD rates, stock prices — with zero relevance to the tenant's pitch. The agent needs a compact relevance filter derived from induction data.

**Solution:** A `build_tenant_search_lens(tenant_id, db)` function that:
1. Reads proposition + GTM learning skills for the tenant
2. Detects recurring signals from keyword patterns in the skill text
3. Outputs a compact 3-part lens: `SIGNALS`, `PROPOSITION`, `IGNORE`
4. Gets injected into the agent system prompt as `SEARCH LENS`

### Lens Format

```
SIGNALS: <comma-separated trigger events — hiring surges, attrition spikes, etc.>
PROPOSITION: <one-line pitch summary — shortest value_prop skill>
IGNORE: <comma-separated consumer noise to filter out>
```

### Injection Points

1. **Agent system prompt** (Context section, right after `INDUCTION: {skills_context}`):
   ```
   SEARCH LENS: {search_lens if search_lens else 'No tenant context — show all relevant news.'}
   ```

2. **Tool-calling principles** (in `AGENT_SYSTEM_PROMPT_BASE`, under web search rule):
   > When searching for news about a company, frame your query and filter results through the SEARCH LENS. Only surface news that signals a potential entry point — a trigger event, pain point, or growth signal relevant to your proposition. Dismiss generic consumer news, stock moves, and product launches.

### Signal Detection

The function scans all proposition + GTM learning skill values (lowercased) for domain keyword patterns:

| Keyword cluster | Signal generated |
|---|---|
| hiring, recruitment, screening, interview | hiring surges, recruitment drives |
| attrition, retention, drop-off, re-hiring | attrition spikes |
| voice ai, conversational ai, ai agent, automation | VoiceAI/automation deployment |
| telecalling, outreach, call center | telecalling operations |
| volume, scale, 10k, mass hiring, bulk | volume increases, workforce scaling |
| frontline, blue-collar, gig worker, delivery partner | frontline workforce expansion, gig worker onboarding |
| funding, series, investment, growth, expansion | funding events, growth/expansion |
| bfsi, bank, insurance, nbfc, branch | branch network changes |
| logistics, 3pl, delivery, fleet, warehouse | logistics network expansion |
| digital, transformation, modernization | digital transformation |

**Causal linking:** If "hiring surges" is detected, "funding events" and "growth/expansion" are automatically added (growth → hiring).

### Proposition Summary

Picks the shortest `value_prop` skill for compact prompt injection. Fallback chain: `value_prop` / `pitch` skills → skills with `platform`/`connect`/`overview`/`ai_hr` in key → any proposition skill.

### Ignore List

Always ignores for B2B tenants: consumer banking products, credit card changes, lounge access, savings account rates, FD rates, personal loan offers. Branch openings are only ignored if "branch network changes" isn't a signal.

### Wire-Up

In the agent chat endpoint (where `system_prompt` is built):
```python
search_lens = build_tenant_search_lens(tenant_id, db)
# ... later:
system_prompt += f"...\nSEARCH LENS: {search_lens or 'No tenant context...'}\n..."
```

Full implementation: `references/tenant-search-lens.md`.

### Pitfall

- **Don't inject at web_search tool level.** Let the LLM construct the query based on the lens in its system prompt. Prepending tenant context to every search query would break generic lookups ("AI voice trends") that aren't company-specific.

## Design Rule for All New Features

Before writing any ARA code, ask these three questions:

1. **Would this feature work for a different tenant with different segments?** If no, it's too Hunar-specific — make it configurable.
2. **Is the config stored in `tenant.config`?** If the answer is a separate table or hardcoded dictionary, move it to tenant.config.
3. **Does the API path include `{tenant_id}`?** Every tenant-scoped endpoint must include it. Platform-level endpoints (cross-tenant admin, billing) do not.

## API Key Resolution Chain

ARA's API key management uses a **three-tier resolution chain**: tenant-level → platform-level → environment variable.

### Resolution Function

```python
def resolve_api_key(service: str, tenant_id: str = None) -> str:
    # 1. Tenant-specific key (stored in tenant.config.api_keys.<service>)
    if tenant_id:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant and tenant.config:
            api_keys = tenant.config.get("api_keys", {})
            if api_keys and service in api_keys and api_keys[service]:
                return str(api_keys[service])
    
    # 2. Platform-wide key (stored in platform_config table)
    row = db.query(PlatformConfig).filter(
        PlatformConfig.key == f"{service}_api_key"
    ).first()
    if row and row.value:
        return row.value
    
    # 3. Env var fallback (legacy)
    env_name = f"{service.upper()}_API_KEY"
    return os.environ.get(env_name, "")
```

**Resolution order:** Priority flows from most specific to most general. A tenant key overrides the platform key, which overrides the env var. This lets you set a single key at platform level for all tenants, then override per-tenant when needed.

### When to Use Each Level

| Level | Scope | When |
|-------|-------|------|
| `tenant.config.api_keys` | Single tenant | Tenant brings their own API key (BYOK) for a premium service |
| `platform_config` table | All tenants | Central key you manage yourself — most common for v1 |
| `env var` | Instance-wide | Legacy fallback — use for bootstrap or when neither DB is available |

### PlatformConfig Table

Defined in `database.py`:

```python
class PlatformConfig(Base):
    __tablename__ = "platform_config"
    id = Column(String, primary_key=True)
    key = Column(String, unique=True, nullable=False)  # e.g. "tavily_api_key"
    value = Column(Text, nullable=False)
    label = Column(String)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    created_at = Column(DateTime, default=utcnow)
```

**No tenant_id** — this is a shared config table, not per-tenant data. Created by `Base.metadata.create_all()` at startup alongside all other tables.

### Wiring Pattern: Tool → Key Resolution

When a tool function needs an API key, the pattern is:

1. Accept an optional `tenant_id` parameter
2. Call `resolve_api_key("service_name", tenant_id)` at invocation time
3. Pass the key to the underlying API call

Example with `web_search()`:

```python
def web_search(query, max_results=5, tenant_id=None):
    api_key = resolve_api_key("tavily", tenant_id)
    if api_key:
        result, err = _search_tavily(query, max_results, api_key)
        if result:
            return result
    result, err = _search_ddg(query, max_results)
    return result or f"Search failed: {err}"
```

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/platform/api-keys` | List platform keys (values masked) |
| `PUT` | `/api/platform/api-keys` | Set key: `{"service":"tavily","value":"sk-..."}` |
| `DELETE` | `/api/platform/api-keys/{service}` | Remove a platform key |
| `GET` | `/api/tenants/{tid}/api-keys` | List tenant keys (masked) |
| `PUT` | `/api/tenants/{tid}/api-keys` | Set tenant key: `{"service":"tavily","value":"sk-..."}` |
| `DELETE` | `/api/tenants/{tid}/api-keys/{service}` | Remove tenant key (falls through) |

**Masking:** Keys are masked in responses (first 4 chars + "****") to avoid leaking secrets in logs or UI.

### Settings UI — Tenant BYOK

The Settings page (`renderSettings()` in `dashboard.js`) includes a **🔑 API Keys** section where tenants can set their own keys:

```
Settings page → 🔑 API Keys section
  ├── Tavily Search (password field, masked)
  └── Leave blank → inherits platform key
```

**Frontend flow:**
1. `renderSettings()` fetches both `/api/tenants/{TENANT}/settings` AND `/api/tenants/{TENANT}/api-keys`
2. Renders key fields with current values (masked) — empty = no tenant override
3. `saveSettings()` saves regular settings first, then PUTs/DELETEs the API key
4. If user clears a key field → DELETE the tenant-level key (falls through to platform)

**Cache busting:** After editing `dashboard.js`, bump the `?v=N` version in `dashboard_template.py`:
```html
<script src="/static/dashboard.js?v=16"></script>
```

### Migration Path

v1 → plaintext storage in `platform_config` and `tenant.config.api_keys`. No encryption.

v1.5 → add `MASTER_ENCRYPTION_KEY` env var + Fernet encryption at rest.

v2 → swap `platform_config` backing for HashiCorp Vault or Doppler (the `resolve_api_key()` abstraction stays the same).

### Pitfalls

- **Key is resolved at call time, not import time:** Don't resolve at module level — resolve dynamically when the tool runs. This ensures tenant context is available and avoids stale env var reads.
- **Mask all key values in API responses:** Never return full keys in list endpoints, logs, or error messages.
- **`resolve_api_key()` creates its own DB session** — it's designed to work from scheduler context (no request-scoped session). This is fine for fast key lookups but check performance if called in hot loops.

## Pitfalls

- **SQLAlchemy `MutableDict` writes are tricky:** `JSON` columns using `MutableDict.as_mutable(JSON)` do NOT support Python truthiness checks (`if not t.config`), direct `__setitem__` after reassignment, or `t.config = {}` the way regular dicts do. The safest write pattern: use raw SQL via `sqlalchemy.text()`:
  ```python
  from sqlalchemy import text
  existing = db.execute(text("SELECT config FROM tenants WHERE id=:id"), {"id": tid}).scalar() or "{}"
  import json
  cfg = json.loads(existing) if isinstance(existing, str) else dict(existing) if existing else {}
  cfg["industry"] = "new value"
  db.execute(text("UPDATE tenants SET config=:cfg WHERE id=:id"), {"cfg": json.dumps(cfg), "id": tid})
  db.commit()
  ```
- **`Column` truthiness:** `if column_name:` is always True in Python since Column objects are truthy. Always use `column_name or ""` or `str(col_val)` to get the actual value.
- **`replace_all` on Similar Code:** The `patch` tool's `replace_all=true` is dangerous when the same code pattern appears in multiple functions with different variable names (e.g., `l.company` vs `lead.company`). Audit ALL matched locations after operation. Better: use unique context strings for individual matches.
- **Empty config is valid:** A new tenant won't have segments configured. Handle this gracefully — show all skills unfiltered, don't crash.
- **Don't hardcode example data:** The segment config examples in this skill are from one tenant. Every new build must check for real tenant data at runtime.

## See Also

- `ara-agent-learning-loop` — Phase 13 covers tenant-specific segments in the context of the learning flywheel
- The `Tenant.config` column in `database.py`
- `server.py` — `load_skills_for_prompt()`, `auto_assign_segment()`, segments API endpoints
