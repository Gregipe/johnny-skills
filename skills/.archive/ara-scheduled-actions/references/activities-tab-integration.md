# Activities Tab Integration — ScheduledActions in `/api/system-jobs`

## Context

The dashboard's Activities tab (`renderActivities()` in `static/dashboard.js`) fetches from TWO endpoints:
- `/api/system-jobs` — displays under "⚙️ System Jobs" section
- `/api/action-items?limit=50` — displays under "🔔 Reminders" section

Originally, `/api/system-jobs` only returned Hermes cron jobs (via `hermes cron list` subprocess). DB ScheduledActions (user crons created via `set_cron` tool) were invisible in the Activities tab.

## Fix (June 10, 2026)

Modified the `/api/system-jobs` endpoint to ALSO return DB ScheduledActions that have a `cron` config in their payload. The endpoint now returns a merged list:

### Endpoint behavior

```python
# GET /api/system-jobs
{
  "jobs": [
    # Hermes cron jobs (prefixed "hermes_")
    {"id": "hermes_abc123...", "name": "...", "schedule": "...", "source": "hermes", ...},
    
    # DB ScheduledActions with cron config (prefixed "db_")
    {"id": "db_311f23fa", "name": "Daily Morning Briefing", "schedule": "daily at 06:30",
     "status": "ok", "source": "scheduled_action", "action_type": "whatsapp_to_owner",
     "deliver": "whatsapp", "next_run": "2026-06-10T12:00:00+05:30",
     "description": "Daily morning briefing with live action items"},
  ]
}
```

### Code structure

```python
@app.get("/api/system-jobs")
def list_system_jobs():
    jobs = []

    # 1. Hermes cron jobs (try/except for missing hermes CLI)
    try:
        r = subprocess.run(...hermes cron list...)
        # parse blocks → jobs list with source="hermes"
    except Exception:
        pass  # hermes CLI not available

    # 2. DB ScheduledActions with cron config
    try:
        db = init_db()
        pending = db.query(ScheduledAction).filter(
            ScheduledAction.tenant_id == TENANT_ID,
            ScheduledAction.status == "pending"
        ).all()
        for a in pending:
            payload = a.payload if isinstance(a.payload, dict) else {}
            cron_info = payload.get("cron", {})
            if cron_info:
                job = {
                    "id": "db_" + a.id,
                    "name": cron_info.get("title", a.action_type),
                    "schedule": f"{freq} at {cron_time}",
                    "status": "ok", "source": "scheduled_action",
                    "action_type": a.action_type,
                    "deliver": a.channel or "whatsapp",
                    "next_run": to_ist(a.scheduled_at),  # ← NO .isoformat() here!
                }
                # Special description for __morning_briefing__
                if msg == "__morning_briefing__":
                    job["description"] = "Daily morning briefing with live action items"
                jobs.append(job)
        db.close()
    except Exception:
        pass

    return {"jobs": jobs}
```

### Pitfalls

1. **`to_ist()` returns a string, not a datetime** — do NOT call `.isoformat()` on it. `to_ist()` already returns a formatted string (e.g., `"2026-06-10T12:00:00+05:30"`). The first version of this code crashed with `AttributeError: 'str' object has no attribute 'isoformat'`. Use `to_ist(a.scheduled_at)` directly.

2. **Hermes CLI may not be in PATH** — The subprocess call is wrapped in try/except because the `hermes` binary might not be available in the ARA server's PATH. Without this guard, the entire endpoint fails and ScheduledActions are never surfaced.

3. **Only actions with `cron` config show** — The Activities tab is designed for recurring system jobs. One-off ScheduledActions (no `cron` payload) are intentionally excluded. They appear in the lead detail panel instead.

4. **ID prefix collision is prevented** — Hermes jobs get `"hermes_"` prefix, DB actions get `"db_"` prefix. No key collision between the two sources.

## Verification

```bash
curl -s http://localhost:8766/api/system-jobs | python3 -c "
import sys,json
d = json.load(sys.stdin)
for j in d.get('jobs', []):
    print(f\"  {j['source']:20s} {j['name'][:40]}\")
"
```
