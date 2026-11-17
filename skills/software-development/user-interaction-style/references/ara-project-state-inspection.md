# ARA Project State Inspection

Quick-reference for resuming work on the ARA dashboard when coming from an interrupted session.

## Quick Checks

```bash
# 1. Is the server running?
ps aux | grep "[p]ython.*server\|[u]vicorn.*8766"

# 2. File modification timestamps (most recently changed = what was being worked on)
cd /Users/greg/ara && ls -lt *.py | head -8

# 3. Database data
sqlite3 ara.db "SELECT COUNT(*) AS leads FROM leads;"
sqlite3 ara.db "SELECT COUNT(*) AS deals FROM deals;"
sqlite3 ara.db "SELECT id, name, phone, stage, assigned_agent FROM leads LIMIT 5;"
sqlite3 ara.db "SELECT COUNT(*) AS actions FROM action_items;"

# 4. Server startup
cd /Users/greg/ara && python3 server.py
# Runs on http://localhost:8766
```

## Key Files

| File | Purpose | Typical State |
|------|---------|---------------|
| `server.py` (2034 lines) | FastAPI backend — all API endpoints | Modified if new endpoints or OAuth fixes |
| `dashboard_template.py` (2118 lines) | Main CRM dashboard HTML/JS | Modified if UI changes or mock data cleanup |
| `threads_template.py` | ChatGPT-style thread manager | Modified if thread list/UI changes |
| `database.py` | SQLite models (Tenant, Lead, Deal, etc.) | Stable once schema is set |
| `whatsapp_manager.py` | WhatsApp Web Playwright automation | Modified if bug fixes or features |
| `email_utils.py` | Gmail/SMTP integration helpers | Modified if email pipeline work |
| `cadence_template.py` (692 lines) | Cadence Builder HTML/JS — 3 template editor | Modified if template rules, steps, or UI changed |
| `induction_engine.py` | LLM-driven induction/onboarding | Stable |

## HTML Pages

| Route | Source | Purpose |
|-------|--------|---------|
| `/` or `/dashboard` | `dashboard_template.py` | Main CRM dashboard |
| `/cadence` | `cadence_template.py` | Cadence Builder — 3-template editor |
| `/threads` | `threads_template.py` | ChatGPT-style thread manager |
| `/leads` | `server.py` (inline HTML) | Simple leads table view |

## API Endpoints (Quick Reference for Dashboard)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/tenants/{id}/leads` | GET | List leads for dashboard/leads page |
| `/api/deals/stats` | GET | Deal pipeline stats (total, by_stage, meetings_booked, closed) |
| `/api/activities?limit=N` | GET | Activity timeline |
| `/api/actions` | GET | Pending action items |
| `/api/deals` | GET | Deal list |
| `/api/knowledge/{tenant_id}` | GET | Uploaded documents |
| `/api/threads/{tenant_id}` | GET | List chat threads |
| `/api/threads/{tenant_id}/{thread_id}` | GET | Thread detail with messages |
| `/api/agent/chat/{tenant_id}` | POST | Chat with Ava (auto-creates thread if no thread_id) |
| `/api/integrations/*` | Various | Integration management |
| `/api/whatsapp/status` | GET | WhatsApp auth state |
| `/api/leads/{lead_id}` | GET/PATCH | Single lead CRUD |

## Priority Items (as of May 23, 2026)

| Priority | Item | Status |
|----------|------|--------|
| P1 | Dashboard mock data cleanup | ✅ Done (real API calls throughout) |
| P1 | Thread continuation bug fix (UnboundLocalError on existing thread_id) | ✅ Done — server.py agent_chat needed `else: thread = db.query(...)` |
| P1 | Web search swapped from DuckDuckGo scraping to Tavily API | ✅ Done — 3 retries with 1s backoff for transient SSL errors |
| P2 | Cadence Builder page | ✅ Built — localhost:8766/cadence, localStorage persistence |
| P2 | Gmail send pipeline | ⏳ Not started |
| P3 | Lead assignment UI | ⏳ Not started |
| P4 | End-to-end verification | ⏳ Not started |

## Server Startup Notes

- Uses `if __name__ == "__main__"` block with `uvicorn.run(app, host="0.0.0.0", port=8766)`
- Depends on: `database.py` (SQLite), `whatsapp_manager.py` (Playwright), `email_utils.py` (smtplib/google API)
- Uses tenant ID `3e736242` hardcoded as `TENANT_ID` constant
- No `.env` needed locally — loads from `~/.hermes/.env` via `load_dotenv()`
- Tavily API key is loaded from `~/.hermes/.env` (`TAVILY_API_KEY`) — used by `web_search()` and `fetch_url()` in server.py
- Web search functions (`web_search`, `fetch_url`) use Tavily API (not DuckDuckGo scraping) with 3-retry logic for transient SSL errors
