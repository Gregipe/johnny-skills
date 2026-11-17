# Data Visibility Audit — May 2026

## Context

Greg stored his WhatsApp number (`919582549236`) via the Settings tab. When he asked Ava "Do you know my number on WhatsApp?", she responded: "I don't have your personal number stored — my database only contains the leads."

This triggered a full audit of what Ava sees vs what the DB stores.

## Discovery Chain

### Step 1: Trace the data path

Settings tab stores phone via:
- `PUT /api/tenants/{tenant_id}/settings` with `owner_phone` → stores in `users.phone`
- `GET /api/tenants/{tenant_id}/settings` returns `admin.phone`

Ava's system prompt is built in `agent_chat()` at server.py line 4522:
1. `ctx = _get_agent_context(tenant_id, db)` — returns context dict
2. `AGENT_SYSTEM_PROMPT_BASE.format(...)` — uses context fields
3. Context section appended at end with time etc.

### Step 2: Find the gap

`_get_agent_context()` at line 6192 returned only:
```python
{"agent_name": agent_name, "owner_name": owner_name, "company": company}
```

No `owner_phone` field. The phone number was in the DB but never surfaced to the LLM.

### Step 3: Check for stale server

After adding `owner_phone` to `_get_agent_context()` and the context section, the fix STILL didn't work. Reason: the running server (PID 44600 on port 8766) was started at 21:01 — BEFORE the edits. A second server was accidentally started on port 8000 (which had the new code) but the WhatsApp coaching flow calls port 8766.

Fix: kill the stale process, restart on the correct port.

### Full Audit Results

| Data | Stored Where | Ava Saw It? | Fix |
|------|-------------|-------------|-----|
| Owner phone | `users.phone` (`919582549236`) | ❌ | Added to `_get_agent_context()` + context section |
| Induction status | `tenants.induction_completed=False, score=75` | ❌ | Added to context + `get_system_map` |
| Email integration | `integration_config` (email-gmail: enabled) | ❌ | Added live status query to context |
| Tenant segments | `tenants.config.segments` (4 segments) | ❌ | Added to `get_system_map` |
| Action items | `action_items` table (4 items) | ❌ | Added `get_action_items` tool |
| Pending scheduled actions | `scheduled_actions` (15 pending) | ❌ | Still not queryable across all leads |
| Logged insights | `ava_insights` (182 total) | ❌ | Still not queryable |
| Coaching history | `coaching_logs` (49 sessions) | ❌ | Still not queryable |

### Code Changes

**1. `_get_agent_context()` — added induction fields:**
```python
induction_completed = bool(tenant.induction_completed) if tenant else False
induction_score = tenant.induction_score if tenant and tenant.induction_score is not None else 0
return {
    "agent_name": ..., "owner_name": ..., "company": ..., "owner_phone": ...,
    "induction_completed": induction_completed,
    "induction_score": induction_score,
}
```

**2. Context section — extended with all new fields:**
```python
system_prompt += f"""
## Context
Current time: ...
Owner WhatsApp: {ctx['owner_phone']}
Induction: {'✅ Complete' if ctx['induction_completed'] else '⚠️ Not yet completed'} | Score: {ctx['induction_score']}/100
Email integration: {email_status}
Pending action items: {pending_actions}
"""
```

**3. `get_system_map` — added `tenant_info`:**
```python
"tenant_info": {
    "industry": tenant.config.get("industry", ""),
    "segments": tenant.config.get("segments", {}),
    "induction_completed": bool(tenant.induction_completed),
    "induction_score": tenant.induction_score,
}
```

**4. `get_action_items` tool — new handler + schema entry**

**5. System prompt guidance — updated to mention new tools**

### Lesson

The root cause was two-fold:
1. **Code gap:** `_get_agent_context()` didn't return owner phone — a prompt-building oversight
2. **Deployment gap:** Stale server process masked the fix — code was correct but never loaded

Code gap → fix in `ara-agent-tools` skill methodology (Data Visibility Audit section)
Deployment gap → fix in `ara-server-healthcheck` skill (wrong-port pitfall)
