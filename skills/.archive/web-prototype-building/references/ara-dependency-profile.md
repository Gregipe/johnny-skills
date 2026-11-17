# ARA Dependency Profile

The ARA server lives at `/Users/greg/ara/` and runs on port 8766.

## Target Python

```
/Users/greg/.hermes/hermes-agent/venv/bin/python3.11
```

This is the Hermes agent venv, not system Python (`/usr/bin/python3`). System Python has `sqlalchemy` but lacks `fastapi`/`uvicorn`.

## Full Dependency Set

Critical server imports checked in order at startup:

| Import | Package | Notes |
|--------|---------|-------|
| `fastapi` | fastapi | v0.133.1 — installed in venv |
| `uvicorn` | uvicorn | v0.41.0 — for `if __name__ == "__main__"` block |
| `sqlalchemy` | sqlalchemy | v2.0.49 — often missing, must install separately |
| `pydantic.BaseModel` | pydantic | Bundled with fastapi |
| `dotenv` | python-dotenv | For loading `~/.hermes/.env` |
| `httpx` | httpx | For LLM API calls and OAuth token exchange |
| `playwright` | playwright + chromium | For WhatsApp automation (optional — server starts without it) |
| `database` | Local | `from database import init_db, ...` |
| `induction_engine` | Local | `from induction_engine import call_llm, ...` |
| `email_utils` | Local | Gmail send pipeline |

## Install Missing Packages

```bash
/Users/greg/.hermes/hermes-agent/venv/bin/python3.11 -m pip install sqlalchemy
```

## Server Start Command

```bash
cd /Users/greg/ara && /Users/greg/.hermes/hermes-agent/venv/bin/python3.11 -u server.py
```

`-u` is critical — unbuffered stdout/stderr so startup messages and crash traces appear in the process log immediately.

## Verifying

```bash
# Quick health check
sleep 3 && curl -s -o /dev/null -w "%{http_code}" http://localhost:8766/dashboard

# Full response test
curl -s http://localhost:8766/dashboard | head -20
```

## Database

SQLite at `ara.db` in the project root. Tables: tenants, leads, deals, deal_events, skills, action_items, conversations, coaching_logs, documents, integration_config, chat_threads, agent_chat_messages.

## Server Source Layout

```
/Users/greg/ara/
├── server.py                  # FastAPI app (~2034 lines)
├── database.py                # ORM models + init_db()
├── dashboard_template.py      # Full CRM UI as Python string (~2118 lines)
├── induction_engine.py        # LLM calls + skill extraction
├── induction_template.py      # Induction chat UI template
├── threads_template.py        # Threads page HTML template
├── whatsapp_manager.py        # Playwright WhatsApp controller
├── email_utils.py             # Gmail SMTP/API utils
├── ara.db                     # SQLite database
└── uploads/                   # Knowledge doc uploads
```
