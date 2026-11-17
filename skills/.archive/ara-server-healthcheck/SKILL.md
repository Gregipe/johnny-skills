---
name: ara-server-healthcheck
description: Full post-restart verification of the ARA server — health checks, UI pages, API endpoints, chat capability, and cleanup of test artifacts. Run this after every server restart.
category: devops
trigger: after restarting the ARA server at localhost:8766
---

# ARA Server Healthcheck

## Trigger

Run this after every ARA server restart to verify everything is functional.

## Server Bring-Up

When the user asks to "bring up" or "restart" the ARA server:

### 🟡 Hard refresh FIRST if template files changed

**If this session modified any server-rendered HTML/JS templates** (`cadence_template.py`, `prompt_builder_template.py`, `dashboard_template.py`, `server.py` with embedded HTML strings, etc.):

**Tell Greg to Cmd+Shift+R (hard refresh) before testing anything.** This is step zero, not troubleshooting step five.

A normal Cmd+R reloads from the browser's disk cache — the old HTML/JS keeps running even though the server has new code. The new code IS on the server, the browser just needs to fetch it fresh. Debugging "the fix isn't working" for an hour when it's just a stale cache is the #1 time-waster after template deployments.

🚫 Do NOT start debugging save issues, JS errors, or visual glitches until the user confirms a hard refresh.
✅ If the user says "it's not working" after a template change, the first thing you say is: "Cmd+Shift+R hard refresh — your browser has cached HTML from before the fix."

### Start the server

```bash
cd /Users/greg/ara && ./venv/bin/python server.py
```

- Use `terminal(background=true, notify_on_complete=true)` for long-running server processes
- **Combined restart** (kill old + start new in separate steps):
  ```bash
  kill $(pgrep -f 'venv/bin/python server.py$') 2>/dev/null
  sleep 2
  cd /Users/greg/ara && nohup ./venv/bin/python server.py &
  ```
  Or use two terminal(background=true) calls: first to kill, second to start.
- **⚠️ pkill race condition:** `pkill -f "venv/bin/python server.py"` also matches the SHELL running the command (since the shell's argv string contains the same pattern). If the shell is killed mid-execution, `sleep` and `nohup` never fire — restart silently fails. Use `kill $(pgrep -f ...)` with a `$` end anchor instead, or do kill + start in separate terminal calls.
- Wait for the "Application startup complete" log line before proceeding
- Do NOT use `&` in the shell command — use the tool's `background=true` flag instead

### Host binding

The server defaults to `host="0.0.0.0"` (all interfaces) in server.py line 7134. If the user explicitly asks for `127.0.0.1`, patch the line before starting:

```
- uvicorn.run(app, host="0.0.0.0", port=8766)
+ uvicorn.run(app, host="127.0.0.1", port=8766)
```

Then start fresh. The old process running on `0.0.0.0` won't automatically pick up the new binding — kill it first.

### 🟡 Troubleshooting: "Not opening in the browser"

When the user reports the server isn't opening in their browser, diagnose before restarting:

1. **Try curl first** — a server can respond to curl but be unresponsive in the browser:
   ```bash
   curl -s -o /dev/null -w "%{http_code} in %{time_total}s\n" http://127.0.0.1:8766/dashboard
   ```
   - No response/connection refused → process is dead. Restart.
   - **200 in < 50ms** → server is network-accessible. The issue is likely a **stale/hung process** from a previous session.

2. **Check log staleness** — `/tmp/ara-server.log` may be from a *previous* instance:
   ```bash
   ls -l /tmp/ara-server.log
   ps -p $(pgrep -f 'venv/bin/python server.py$') -o lstart=
   ```
   If the log predates the running process, the current server's stdout isn't redirected — making diagnostics impossible. **Restart with output redirected.**

3. **Restart cleanly** — kill the old process, start fresh with `terminal(background=true)`:
   ```bash
   kill $(pgrep -f 'venv/bin/python server.py$') 2>/dev/null
   ```
   Then start via `terminal(background=true, ...)` so the tool tracks output.

4. **Verify after restart** — confirm new PID is younger than file mtime, then verify via curl.

### 🔴 Verify the PORT before starting — don't assume 8766

The server runs on port 8766 (`server.py` line 8215: `uvicorn.run(app, host="127.0.0.1", port=8766)`).
**Verify this line before starting.** Do NOT assume the port from memory. Common mistake: starting on 8000 (default uvicorn) while the real server is on 8766.

**If you started on the wrong port:**
1. The port-8000 process gets requests but the WhatsApp coaching flow (`http://localhost:8766/api/agent/chat/{id}` at line 7562) hits 8766 — the old/stale server
2. Greg tests on 8766, sees OLD behavior, and reports your fix "didn't work"
3. You debug the code while a stale process serves the real port

**⚠️ You can have TWO servers running simultaneously** — one on the wrong port (8000) and one on the right port (8766). Code changes you make go to disk, but the 8766 server may be a stale process started BEFORE your edits. The 8000 server has your new code but no one hits it. Always check `lsof -i :8766` for the PID, then `ps -p <pid> -o lstart=` vs file mtime to confirm it's fresh.

**Check which port before starting:**
```bash
grep "uvicorn.run" /Users/greg/ara/server.py
```

**Always kill the process on the CORRECT port, not your assumed one:**
```bash
lsof -i :8766  # finds the right process
kill <pid>
```

### ⚠️ Verify PID start time vs file modification time

After starting, confirm the process loaded the latest code:

```bash
echo "PID start: $(ps -p $(pgrep -f 'venv/bin/python server.py$') -o lstart= 2>/dev/null)"
echo "File mtime: $(ls -l /Users/greg/ara/server.py | awk '{print $6,$7,$8}')"
```

The PID start time must be **after** the file modification time. If it's before, the process is running stale code — kill it (`kill <pid>`) and restart.

For git-tracked files, check vs commit time instead:
```bash
echo "Server: $(ps -p $(pgrep -f 'venv/bin/python server.py$') -o lstart= 2>/dev/null)"
echo "Commit: $(cd /Users/greg/ara && git log -1 --format='%ai %s')"
```

This catches the common case where `pkill` or `kill` silently fails (wrong pattern, race condition) and the "new" server is actually the OLD process still running.

### ⚠️ Scan startup logs for errors

**Before running any healthcheck**, scan the startup output (returned via `notify_on_complete`) for ERROR lines — especially `[scheduler] ERROR` and `[whatsapp] ERROR`. The server may start successfully but have broken subsystems:

```bash
# Check for scheduler errors in the startup output
grep -c "ERROR" <<< "$STARTUP_OUTPUT"
grep -i "ERROR\|Traceback\|missing" <<< "$STARTUP_OUTPUT"
```

Common patterns to look for:
- `send_via_gmail_api() missing 1 required positional argument: 'body'` — means `_execute_action` in server.py is calling the function with wrong positional args (e.g. `send_via_gmail_api(lead.email, subject, body)` instead of `send_via_gmail_api(tokens, lead.email, subject, body)`). The fix is to look up OAuth tokens from `IntegrationConfig` and pass them as the first argument.
- Any `[scheduler] ERROR` — check `_execute_action` for the matching action type.

**Fix bugs proactively** — Greg expects a Chief of Staff to find and fix issues without being asked. If the error is a clear code bug (wrong args, missing import, etc.), fix it, restart, and verify before reporting.

11. **Cadence configs can be empty or have null timings** — The most common cause of "Ava ran into a system error" when starting an outbound cadence. Check `references/debugging-tool-execution.md` for the diagnostic chain: empty steps, null delay_hours, SQLAlchemy JSON mutation bug, and the misleading "All actions completed successfully" message.

12. **Sidecar health is part of server health** — The ARA server depends on the WhatsApp sidecar (port 8767). After restarting ARA, always verify the sidecar is connected too: `curl -s http://localhost:8767/status`. The scheduler auto-starts the sidecar on boot, but if it's in a reconnect cycle, the sidecar returns `connected: false`. Wait for it to come back before testing WhatsApp features.

13. **Zombie process on port — lsof shows LISTEN but server doesn't serve** — After a hard kill (SIGKILL/exit 137 from macOS Jetsam), `lsof -i :8766` may show a process PID still holding the port as LISTEN, but the server is COMPLETELY unresponsive — not even `/docs` returns HTML. The OS keeps the TCP socket alive even though the process can't handle requests. This is distinct from the EADDRINUSE race condition (pitfall #14): the port binds successfully on restart, but the zombie PID won't release until killed.

    **Detection:** Always verify responsiveness with BOTH checks:
    ```bash
    lsof -i :8766
    curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://localhost:8766/docs
    ```
    If LISTEN but 000 (timeout), the process is a zombie. Kill it and restart.

    **Fix:** Nuke every PID on the port:
    ```bash
    lsof -ti:8766 | xargs kill -9 2>/dev/null
    sleep 2
    ```
    Verify freed (`lsof -i :8766` returns nothing) before starting the new server.

14. **Port-binding race condition after kill** — When killing the old ARA process and immediately starting a new one, port 8766 may still be in use. The new process exits with code 1 and `[Errno 48] error while attempting to bind on address ('127.0.0.1', 8766): address already in use`. The old process's PID is still in the kernel socket TIME_WAIT state, or there's another orphaned uvicorn process on the port.

    **Fix:** Use `lsof -ti:8766` to find ALL processes holding the port, then force-kill them:
    ```bash
    lsof -ti:8766 | xargs kill -9 2>/dev/null
    sleep 2
    ```
    Then start the new server. `kill $(pgrep -f ...)` alone may not catch orphaned uvicorn worker processes that the old server spawned.

15. **Offset-naive vs offset-aware datetime crash** — The `_engagement_stage()` function in server.py at line 5103 calls `(utcnow() - l.last_contacted_at).days`. `utcnow()` returns timezone-aware (`datetime.now(timezone.utc)`), but DB timestamps are offset-naive. This raises `TypeError: can't subtract offset-naive and offset-aware datetimes` and causes an HTTP 500 on the `/api/agent/chat/{tenant_id}` endpoint.

    **Symptom:** Every chat question crashes with "Internal Server Error" even though the server starts normally and `/docs` responds fine.

    **Fix:** Use `datetime.utcnow()` (offset-naive) instead of `utcnow()` for this comparison, since DB values are naive:
    ```python
    days_since = (datetime.utcnow() - l.last_contacted_at).days if l.last_contacted_at else 7
    ```
    `datetime` is already imported at the top of server.py: `from datetime import datetime, timezone, timedelta`.

    **Detection:** Check the stderr log for `TypeError: can't subtract offset-naive and offset-aware datetimes.`

15. **WhatsApp self-chat healthcheck triggers a real coaching response** — Step 3a calls `POST /api/whatsapp/inbound` which the ARA server processes like a real self-chat: thumbsup reaction (silent fail if fake JID), typing keepalive, and Ava LLM response. Consumes tokens. Skip step 3a during dev testing.

16. **Self-chat test requires `user.lid` to be populated** — The test extracts LID from `/status` to build the payload. If the sidecar just authenticated and `sock.user.lid` isn't populated yet (timing issue), the test payload will have a bad `remote_jid`. Wait a few seconds after sidecar reconnect before running.

17. **Coaching loop detection in logs** — After any restart involving the WhatsApp pipeline, check for cascading coaching responses: `grep "Coaching response sent" /tmp/ara-stderr.log | wc -l`. More than 1 response per test message indicates a loop. Also check `grep -c "sentMsgIds has|forwardedMsgIds has" /tmp/sidecar-fresh.log` — these should be non-zero (dedup is working). If both are zero, the messages.upsert handler isn't checking either set.

18. **Rate limiter silently drops, not errors** — The coaching rate limiter (`_check_coach_rate_limit` in server.py) returns False silently — no HTTP error, no response to the user. If coaching seems intermittently unresponsive, check `grep "coach_rate_limit" /tmp/ara-stderr.log` for rate-limit hits. This is tripped by 4+ messages in 30 seconds.

## Launchd Deployment (macOS Auto-Restart)

The ARA server can be deployed as a macOS launchd service for automatic crash recovery and login-time startup.

### Plist Location

`~/Library/LaunchAgents/com.ara.server.plist`

### Plist Template

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ara.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/greg/ara/venv/bin/python</string>
        <string>-u</string>
        <string>/Users/greg/ara/server.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/greg/ara</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>5</integer>
    <key>StandardOutPath</key>
    <string>/Users/greg/ara/logs/server.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/greg/ara/logs/server-err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/greg/ara/venv/bin:/Users/greg/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

### Commands

| Action | Command |
|--------|---------|
| Load/start | `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ara.server.plist` |
| Unload/stop | `launchctl bootout gui/$(id -u)/com.ara.server` |
| Restart (force kill + reload) | `launchctl kickstart -k gui/$(id -u)/com.ara.server` |
| Status | `launchctl print gui/$(id -u)/com.ara.server` |

### Key Details

- **PATH is critical:** launchd services have a minimal default PATH (`/usr/bin:/bin`). The scheduler spawns the Baileys sidecar via subprocess, which needs `node` in PATH. Always include `~/.local/bin` (where node lives) and `/opt/homebrew/bin` in the plist's EnvironmentVariables.
- **Restarts on crash:** `KeepAlive=true` + `ThrottleInterval=5` means the server restarts within 5 seconds of any crash (including SIGKILL from macOS memory pressure).
- **Logs go to `~/ara/logs/`:** stdout → server.log, stderr → server-err.log. Create the directory before loading.
- **Zombie process on port (pitfall #13):** After launchd takes over, the old manually-started server may remain as a zombie holding port 8766. `lsof -i :8766` shows LISTEN but curl times out. `lsof -ti:8766 | xargs kill -9` before loading the plist.
- **Scheduler spawns sidecar on each restart:** Every time the ARA server starts (including crash recovery), the scheduler spawns a new Baileys sidecar. If the old sidecar still holds port 8767, the new one dies with EADDRINUSE. This is benign — the old sidecar continues working. But it means the scheduler's "Baileys sidecar responsive" log line may be misleading (it could be hitting the old sidecar's health endpoint, not the one it just spawned).
- **Multiple restarts = multiple sidecar spawn attempts:** If the server crashes and restarts multiple times (e.g., during launchd setup), each restart spawns a new sidecar attempt. The scheduler doesn't check if the sidecar process it spawned is actually alive — it only checks port responsiveness. Downside: each spawn logs "Baileys sidecar started (PID X)" despite the process dying immediately from EADDRINUSE.

### Verify it's live

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8766/
# Must return 200
```

Then proceed to the full healthcheck below. Uses a dedicated test tenant to avoid polluting real data. Creates temp artifacts, validates them, **deletes everything** before finishing.

## Quick Invocation

### CLI command (standalone, no agent needed)

```bash
ara-healthcheck
```

Installed at `~/bin/ara-healthcheck` (Python script, executable). PATH set in `.zshrc`. Runs the full healthcheck and cleans up after itself — no Hermes agent required.

### Via agent (from chat)

Just say **"run healthcheck"** — loads this skill and executes it.

### Via cron (for auto-verification after restart)

Not currently cronned, but can be set up with `cronjob action=create prompt="Run ara-server-healthcheck" schedule="5 * * * *"` for hourly verification.

## Prerequisites

- Server running at `http://localhost:8766`
- ARA DB at `/Users/greg/ara/ara.db`
- Python: `/Users/greg/.hermes/hermes-agent/venv/bin/python3.11` (the only env with fastapi installed — NOT `venv/bin/python` or system python)

## Steps

### 1. Server Health

- `curl -s -o /dev/null -w "%{http_code}" http://localhost:8766/` → **200**
- `curl -s -o /dev/null -w "%{http_code}" http://localhost:8766/dashboard` → **200**

**Quick sanity** (single-line dashboard + API check):

```bash
D=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8766/dashboard)
S=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8766/api/action-items/stats)
echo "dashboard=$D action-items=$S"
# Expect: dashboard=200 action-items=200
```

### 2. Init Tenant & Lead Counts

Fetch existing tenant and count baseline:

```bash
TENANTS=$(curl -s http://localhost:8766/api/tenants)
LEAD_COUNT=$(echo "$TENANTS" | python3 -c "import sys,json; data=json.load(sys.stdin); print(data[0]['lead_count'] if data else 0)")
TENANT_ID=$(echo "$TENANTS" | python3 -c "import sys,json; data=json.load(sys.stdin); print(data[0]['id'] if data else '')")
```

Record `LEAD_COUNT` as baseline — final check must return to this count.

### 3. UI Pages Load (HTML 200)

Verify all HTML-rendering pages return 200:

| Page | Endpoint |
|------|----------|
| Landing | `GET /` |
| Dashboard | `GET /dashboard` |
| Threads | `GET /threads` |
| Cadence Builder | `GET /cadence` |
| Induction | `GET /induction` |
| WhatsApp Link | `GET /api/whatsapp/link` |

**Additionally**, for the threads page, verify rendered content (not just HTTP 200) — a broken HTML comment causes the page to return 200 with blank DOM. Check that `id="threadCount"` exists in the response:

```bash
curl -s http://localhost:8766/threads | grep -c 'id="threadCount"'
# Must return >= 1
```

### 3a. WhatsApp Sidecar & Self-Chat Pipeline

Verify the WhatsApp sidecar is healthy and the self-chat coaching pipeline works end-to-end:

```bash
# 1. Sidecar status + user info
SIDECAR=$(curl -s http://localhost:8767/status)
SIDECAR_CONNECTED=$(echo "$SIDECAR" | python3 -c "import sys,json; print(json.load(sys.stdin).get('connected', False))")
SIDECAR_LID=$(echo "$SIDECAR" | python3 -c "import sys,json; print(json.load(sys.stdin).get('user',{}).get('lid','MISSING'))")
echo "sidecar_connected=$SIDECAR_CONNECTED user_lid=$SIDECAR_LID"

# 2. Typing endpoint responds
TYPING_TEST=$(curl -s -X POST http://localhost:8767/api/typing \
  -H "Content-Type: application/json" \
  -d '{"jid":"00000000000@s.whatsapp.net","action":"paused"}')
echo "typing_endpoint=$TYPING_TEST"

# 3. Test self-chat webhook on ARA: simulate owner sending to self
SELF_CHAT_TEST=$(curl -s -X POST http://localhost:8766/api/whatsapp/inbound \
  -H "Content-Type: application/json" \
  -d "{\"phone\":\"$(echo \"$SIDECAR\" | python3 -c \"import sys,json; print(json.load(sys.stdin).get('user',{}).get('phone',''))\")\",\"name\":\"Owner\",\"message\":\"[HEALTHCHECK] Self-chat test\",\"owner_reply\":true,\"message_id\":\"hc_$(date +%s)\",\"remote_jid\":\"$(echo \"$SIDECAR_LID\" | sed 's/:.*$//')@lid\"}")
echo "self_chat_webhook=$SELF_CHAT_TEST"

# 4. Verify response
echo "$SELF_CHAT_TEST" | python3 -c "import sys,json; r=json.load(sys.stdin); assert r.get('status')=='ok', f'Expected ok, got {r}'; print('self-chat pipeline: OK')"
```

### 4. Core API Read Endpoints

| Endpoint | Expects |
|----------|---------|
| `GET /api/tenants` | 200, array |
| `GET /api/deals` | 200, array |
| `GET /api/deals/stats` | 200 |
| `GET /api/activities` | 200, array |
| `GET /api/insights` | 200, array |
| `GET /api/insights/stats` | 200 |
| `GET /api/learning/stats` | 200 |
| `GET /api/actions` | 200, array |
| `GET /api/actions/stats` | 200 |
| `GET /api/action-items` | 200, array |
| `GET /api/action-items/stats` | 200 |
| `PATCH /api/action-items/{id}` | 200 (test with add-then-resolve) |
| `GET /api/agent/suggestions/{tenant_id}` | 200 |
| `GET /api/whatsapp/status` | 200 |
| `GET /api/integrations` | 200, array with live-status fields |
| `GET /api/integrations/{id}/status` | 200 (test for email-gmail, whatsapp-self) |
| `GET /api/threads/{tenant_id}` | 200, array |
| `POST /api/threads/bulk-delete` | 200 (test with empty IDs) |

### 5. Create & Verify Test Lead

Use a clearly identifiable test name so cleanup is reliable:

```bash
TEST_LEAD=$(curl -s -X POST "http://localhost:8766/api/tenants/$TENANT_ID/leads" \
  -H "Content-Type: application/json" \
  -d '{"name":"[HEALTHCHECK] Test Lead","email":"healthcheck@test.local","phone":"+919999999999","company":"HealthCheck Inc","lead_source":"test"}')
LEAD_ID=$(echo "$TEST_LEAD" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
```

Verify:
- `GET /api/leads/{lead_id}` → returns lead with matching fields
- `GET /api/leads/search?q=HealthCheck` → finds it
- `PATCH /api/leads/{lead_id}` with `{"notes": "verified"}` → returns 200 with `{"status": "ok"}` (not the full object — verify update via GET after)
- `GET /api/leads/check-duplicate?phone=+919999999999` → finds duplicate

### 6. Create & Verify Test Deal

```bash
TEST_DEAL=$(curl -s -X POST "http://localhost:8766/api/deals" \
  -H "Content-Type: application/json" \
  -d '{"org_name":"[HEALTHCHECK] Test Corp","stage":"new","contact_name":"Test Contact","expected_value":1000}')
DEAL_ID=$(echo "$TEST_DEAL" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))")
```

Verify:
- `GET /api/deals/{deal_id}` → returns deal
- `PATCH /api/deals/{deal_id}` with `{"stage": "qualified"}` → 200
- `POST /api/deals/{deal_id}/attach-lead` with `{"lead_id": "$LEAD_ID"}` → 200

### 7. Test Chat Capability

Create a chat thread and send a message:

```bash
# Start lead chat
THREAD=$(curl -s -X POST "http://localhost:8766/api/leads/$LEAD_ID/chat")
THREAD_ID=$(echo "$THREAD" | python3 -c "import sys,json; print(json.load(sys.stdin)['thread_id'])")

# Send a message via agent chat
CHAT_RESP=$(curl -s -X POST "http://localhost:8766/api/agent/chat/$TENANT_ID" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Hi Ava, this is a healthcheck test message. Please confirm you are operational.\",\"thread_id\":\"$THREAD_ID\"}")
```

Verify response contains `"response"` key with non-empty text, and `"thread_id"` matches.

### 8. Verify Conversation Storage

```bash
# Get thread with messages
THREAD_DATA=$(curl -s "http://localhost:8766/api/threads/$TENANT_ID/$THREAD_ID")
```

Verify it contains at least 2 messages (user + assistant).

### 9. Test Learning & Insights Pipeline

- `POST /api/conversations` (create a test conversation for the test lead)
- `POST /api/conversations/{conversation_id}/extract-insights` (extract)
- `GET /api/insights?lead_id=$LEAD_ID` (should find extracted insight)
- `GET /api/learning/notifications` (200, array)

### 10. Test Cadence Preview

```bash
CADENCE=$(curl -s -X POST "http://localhost:8766/api/cadence/preview" \
  -H "Content-Type: application/json" \
  -d '{"source":"form","stage":"new"}')
```

Verify returns 200 with stages array.

### 11. Test Knowledge Docs

- `GET /api/knowledge/{tenant_id}` → 200, array

### 12. Test Coaching

- `POST /api/tenants/{tenant_id}/coaching` with valid coaching data → 200  
  **Schema:** `{"feedback_type": "call|email|general", "context": "healthcheck", "feedback": "[HEALTHCHECK] ..."}`  
  *(Do NOT use `title` or `content` — the endpoint requires `feedback_type`, `context`, and `feedback`)*
- `GET /api/tenants/{tenant_id}/coaching` → 200, array with the new entry

### 13. Bulk Operations

- `POST /api/leads/bulk-delete` with test lead ID → 200

### 14. CLEANUP — Remove All Test Artifacts

**This is critical.** Every artifact created during this healthcheck must be deleted.

```bash
# Delete test deal (detaches leads first)
curl -s -X DELETE "http://localhost:8766/api/deals/$DEAL_ID" > /dev/null

# Delete test thread
curl -s -X DELETE "http://localhost:8766/api/threads/$TENANT_ID/$THREAD_ID" > /dev/null

# Find and delete any remaining healthcheck leads (search-based cleanup)
HEALTHCHECK_LEADS=$(curl -s "http://localhost:8766/api/leads/search?q=HEALTHCHECK")
HEALTHCHECK_LEAD_IDS=$(echo "$HEALTHCHECK_LEADS" | python3 -c "
import sys, json
leads = json.load(sys.stdin)
for l in leads:
    if '[HEALTHCHECK]' in l.get('name', '') or 'healthcheck@test.local' in l.get('email', ''):
        print(l['id'])
")

for lid in $HEALTHCHECK_LEAD_IDS; do
  curl -s -X PATCH "http://localhost:8766/api/leads/$lid" -H "Content-Type: application/json" -d '{"stage":"dormant"}' > /dev/null
  curl -s -X PATCH "http://localhost:8766/api/leads/$lid" -H "Content-Type: application/json" -d '{"assigned_agent":"healthcheck"}' > /dev/null
done

# Bulk delete remaining healthcheck leads
curl -s -X POST "http://localhost:8766/api/leads/bulk-delete" \
  -H "Content-Type: application/json" \
  -d "{\"lead_ids\": $(echo $HEALTHCHECK_LEAD_IDS | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip().split()))")}" > /dev/null

# Delete any test coaching logs / conversations (no DELETE endpoint exists — entries persist but are tagged [HEALTHCHECK] and benign)
curl -s "http://localhost:8766/api/tenants/$TENANT_ID/coaching" | python3 -c "
import sys, json
items = json.load(sys.stdin)
for i in items:
    if '[HEALTHCHECK]' in str(i):
        print('NOTE: coaching entry', i.get('id'), 'cannot be deleted via API')
" 
```

### 15. Final Verification

- Confirm lead count returned to baseline
- Confirm no `[HEALTHCHECK]` or `healthcheck@test.local` records exist
- Confirm no test threads remain

### 15a. Verify Coaching Rate Limiter

After the infinite loop fix, confirm the rate limiter is active and doesn't interfere with normal operation:

```bash
# Simulate 4 rapid coaching pings to verify rate limiter activates on #4
TENANT_ID=$(curl -s http://localhost:8766/api/tenants | python3 -c "import sys,json; data=json.load(sys.stdin); print(data[0]['id'] if data else '')")
for i in 1 2 3 4; do
  RESULT=$(curl -s -X POST "http://localhost:8766/api/whatsapp/inbound" \
    -H "Content-Type: application/json" \
    -d "{\"phone\":\"919999999999\",\"name\":\"Owner\",\"message\":\"[RATE TEST $i] coaching check\",\"owner_reply\":true,\"message_id\":\"rate_test_$i\",\"remote_jid\":\"rate_test_jid\"}")
  echo "Request $i: $(echo $RESULT | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"status\",\"unknown\"))')"
  sleep 1
done
# Check that rate_limiter warning appears in logs
grep "coach_rate_limit" /tmp/ara-stderr.log
```

Expect: Requests 1-3 return `ok`, request 4 returns `ok` or `skipped` (server doesn't return error, just silently drops). Rate limiter log line should appear for request 4.

### 16. Report

Output a summary:
```
✅ Server Health: OK
✅ UI Pages: N/N loaded
✅ WhatsApp Sidecar: Connected/LID present
✅ Gmail Integration: Connected/Disconnected
✅ Self-Chat Pipeline: Pass/Fail
✅ Core API: N/N endpoints verified
✅ Chat: Pass/Fail
✅ Lead CRUD: Pass/Fail
✅ Deal CRUD: Pass/Fail
✅ Learning Pipeline: Pass/Fail
✅ Cleanup: Clean/Failures
```

## Standalone CLI

## Pitfalls

1. **Thread and deal cleanup ordering** — Delete deals first (they can reference leads), then threads, then leads. Reverse order causes FK errors.
2. **Test name tagging** — Always prefix test artifacts with `[HEALTHCHECK]` so bulk cleanup via search is reliable. Never use real-looking names for test data.
3. **Cadence auto-scheduling** — Creating a lead may auto-schedule cadence actions. The bulk-delete endpoint should cascade-clean these, but verify `GET /api/actions?lead_id=$LEAD_ID` returns empty after cleanup.
4. **Concurrent runs** — Only run one healthcheck at a time. Parallel runs create duplicate test artifacts and race on cleanup.
5. **WhatsApp status** — The `/api/whatsapp/status` endpoint may show "disconnected" which is fine — the healthcheck validates the endpoint responds, not the connection state.
6. **Threads page: 200 OK ≠ content OK** — A broken HTML comment (e.g., `<!-- comment ── →` with Unicode arrow instead of `-->`) causes the threads page to return HTTP 200 with a completely blank center panel and zero browser console errors. Always verify `id="threadCount"` or `id="threadList"` exist in the response HTML, not just the HTTP status code.

7. **Integration status is live-checked, not cached** — `GET /api/integrations` calls the Gmail OAuth refresh endpoint, SMTP login, or WhatsApp status sync on every request. A Gmail integration with expired/revoked OAuth tokens correctly shows `connected: false` even if the DB row exists. Don't treat a disconnected-status as a bug — it means the integration needs re-authentication.

8. **Static file cache busting** — When editing `static/dashboard.js`, browsers cache aggressively. The cache buster is hardcoded in `dashboard_template.py` as `<script src="/static/dashboard.js?v=N">`. **Every dashboard.js change MUST bump `N`** (e.g. `v=22` → `v=23`) before deploying — without it, users see the old JS until they manually hard-refresh. If the user reports "the fix isn't working" after a JS deploy, cache is the #1 suspect. Do not rely on `?t=` query params on the page URL — those only bust the HTML cache, not the JS subresource.

9. **Gmail integration status must be live-checked, not DB-only** — The `/api/integrations/email-gmail/status` endpoint calls `_live_check_email()` which hits the Google OAuth refresh endpoint. A DB record with `enabled=True` and valid-looking tokens can STILL report `connected: false` if the access token has expired and the refresh fails (e.g., stale `client_id`/`client_secret`, revoked refresh token). Check `expiry` in the config — if >7 days old, flag re-authentication.

10. **Failed scheduled actions are silently logged, not alerted** — When the scheduler permanently fails an action, it creates a `LearningNotification` of type `action_failed` but never pushes a WhatsApp alert. The healthcheck should proactively query for failed actions and report them:
    ```bash
    curl -s http://localhost:8766/api/learning/notifications?types=action_failed | python3 -c "
    import sys, json
    notifs = json.load(sys.stdin)
    if notifs:
        for n in notifs:
            print(f'⚠️ {n[\"title\"]}: {n[\"message\"][:80]}')
    else:
        print('No failed actions')
    "
    ```

11. **macOS `/opt/ara` doesn't exist by default (CRITICAL)** — The server hardcodes `/opt/ara/ara.db`, `/opt/ara/.env`, and `/opt/ara/uploads`. On macOS, `/opt` is root-owned and `/opt/ara` doesn't exist. If you start the server without creating it first, the server creates a fresh empty `ara.db` at `/opt/ara/ara.db` — all real leads/deals vanish from the API because it's looking at the wrong database. The old DB at `/Users/greg/ara/ara.db` is untouched but the server ignores it.

    **Symptoms:** `/api/tenants` returns empty array `[]`, `/api/deals/stats` returns all zeros, but the server returns 200 on `/` and `/dashboard`.

    **Fix:** Create `/opt/ara` and copy the real database over:
    ```bash
    sudo mkdir -p /opt/ara/uploads && sudo chown greg /opt/ara /opt/ara/uploads
    cp /Users/greg/ara/ara.db /opt/ara/ara.db
    # .env is optional — copy if it exists
    cp /Users/greg/ara/.env /opt/ara/.env 2>/dev/null
    ```

    **Detection:** If the healthcheck's tenant query returns empty `[]`, check `ls -la /opt/ara/ara.db` — if it was just created (timestamp matches server start time), it's a fresh empty DB. Compare lead counts against `/Users/greg/ara/ara.db`.

12. **Gmail OAuth "deleted_client" error** — When the Google Cloud OAuth client is deleted, the integration shows `enabled=True` in the DB but the access token is expired and refresh returns HTTP 401 with `{"error": "deleted_client"}`. The `_live_check_email()` in server.py returns `False`, and `/api/integrations` reports `connected: false`. The inbox email poller (`_poll_inbound_gmail`) silently returns 0 on every cycle — no crashes, no noise, but no email processing.

    **Diagnosis:** Test the token directly:
    ```bash
    cd /Users/greg/ara && venv/bin/python -c "
    import json, sqlite3, urllib.request
    db = sqlite3.connect('/opt/ara/ara.db')
    row = db.execute(\"SELECT config FROM integration_config WHERE integration_id='email-gmail'\").fetchone()
    config = json.loads(row[0])
    req = urllib.request.Request(
        'https://gmail.googleapis.com/gmail/v1/users/me/profile',
        headers={'Authorization': f'Bearer {config[\"access_token\"]}'},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        print('Token OK:', json.loads(resp.read()).get('emailAddress'))
    except urllib.error.HTTPError as e:
        print(f'HTTP {e.code}: {e.read().decode()[:200]}')
    "
    ```

    **Fix:** Re-authenticate Gmail — either create a new OAuth client in Google Cloud Console, or switch to Gmail App Password + IMAP. The inbox email poller starts working immediately once auth is valid.

    See `references/gmail-oauth-diagnostics.md` for the full diagnostic procedure.

13. **Duplicate server start on kill+start race** — When you `kill $(pgrep ...)` then immediately `terminal(background=true)` to start the server, the kill may not release port 8766 before the new process tries to bind. The SECOND start fails with `[Errno 48] address already in use`, but the FIRST start (the kill's target) resumes. You end up with 200 on curl but the server may be the OLD process running stale code.

    **Detection:** After any kill+start sequence, verify the PID is new:
    ```bash
    # Check the PORT is held by a brand-new PID
    lsof -i :8766 | grep LISTEN
    ps -p <pid> -o lstart=
    # PID start time must be AFTER your code changes
    ```

    **Fix:** Kill, wait, THEN start in a separate `terminal()` call:
    ```bash
    # Step 1: Kill
    lsof -ti:8766 | xargs kill -9 2>/dev/null
    # Step 2: Wait (separate terminal call)
    sleep 3
    # Step 3: Start (separate terminal call, background=true)
    cd /Users/greg/ara && ./venv/bin/python -u server.py
    ```




