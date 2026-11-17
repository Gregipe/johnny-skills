# Scheduler Error Patterns Found in ARA Startup Logs

## `send_via_gmail_api() missing 1 required positional argument: 'body'`

**Error line in logs:**
```
[scheduler] ERROR: Scheduled action 6c81a401 permanently failed: send_via_gmail_api() missing 1 required positional argument: 'body'
```

**Root cause:** `_execute_action()` in `server.py` calls `send_via_gmail_api(lead.email, subject, body)` — but the function signature is:
```python
def send_via_gmail_api(tokens: dict, to: str, subject: str, body: str, ...)
```

Three positional args were passed for a four-parameter function:
- `lead.email` landed in `tokens` (wrong type — should be a dict)
- `subject` landed in `to` (subject becomes the "to" field)
- `body` landed in `subject` (body becomes the subject)
- `body` is never provided → error

**Fix (server.py, `_execute_action`):**
```python
elif action.action_type == "email":
    subject = payload.get("subject", "Follow-up")
    body = payload.get("body", "")
    if lead and lead.email and body:
        # Look up Gmail OAuth tokens from integration config
        tokens = None
        gmail_cfg = db.query(IntegrationConfig).filter_by(
            tenant_id=action.tenant_id,
            integration_id="email-gmail",
            enabled=True,
        ).first()
        if gmail_cfg and isinstance(gmail_cfg.config, dict):
            tokens = gmail_cfg.config
        if tokens:
            send_via_gmail_api(tokens, lead.email, subject, body)
```
