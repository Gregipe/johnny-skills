# Gate Test Methodology for Ava

Gate tests are self-contained Python scripts that run against the production server (46.224.132.99) to verify behavioral correctness after code changes. Each Fix has its own gate script that seeds test data, calls the API, and verifies assertions against responses and tool calls.

## Pattern

```python
import sqlite3, subprocess, json, time, uuid

URL = "http://localhost:8766/api/agent/chat/3e736242"
TENANT = "3e736242"

def new_thread(label):
    db = sqlite3.connect('/opt/ara/ara.db')
    tid = uuid.uuid4().hex[:8]
    db.execute("INSERT INTO chat_threads (...) VALUES (...)", (tid, TENANT, ...))
    db.commit(); db.close()
    return tid

def call(msg, tid):
    resp = subprocess.run(["curl", "-s", "-X", "POST", URL, ...], capture_output=True, timeout=60)
    data = json.loads(resp.stdout) if resp.stdout else {}
    return data.get("response", ""), data.get("tool_results")
```

## Methodology Rules

1. **Fresh thread per test** — Always `new_thread()` to avoid contaminating other tests or the coaching thread.
2. **Assert on tool calls AND prose** — Check `tool_results` for correct tools called AND `response` for correct behavior. The two must agree (no claim-without-call).
3. **SSH for log verification** — Use `subprocess.run(["ssh", "root@46.224.132.99", cmd])` to check server/sidecar logs. Direct DB access via SSH python3.
4. **Cleanup after** — Seed data with identifiable prefixes (`Test overdue 1:`) and delete after test: `db.execute("DELETE FROM action_items WHERE title LIKE 'Test%'")`.
5. **Voice notes force confirmation** — Use `🎤 [VOICE NOTE — do NOT use [ACTION: NOW].]\n\n...` prefix so the LLM registers it as a voice note (forces pending creation).
6. **Wait between calls** — `time.sleep(2-4)` between sequential API calls to allow the observe loop + pending flow to complete.
7. **Grep the codebase for deleted guards** — After each delete-Fix, assert zero matches: `ssh("cd /opt/ara && grep -c 'guard_name' server.py") == "0"`.
8. **Pipeline nouns test** — After Fix 1, assert no capability-list or pipeline-specific nouns appear in smalltalk/status responses.
9. **Write-read consistency** — After any write command, follow up with a read to verify the DB reflects what the LLM reported.
10. **Partial snapshot test** — Seed >7 items, ask "what's overdue?", verify `get_action_items` was called (not just block).

## Deploy Pattern

After each fix:
```bash
scp /tmp/fix_N.py root@46.224.132.99:/tmp/
ssh root@46.224.132.99 "python3 /tmp/fix_N.py"
ssh root@46.224.132.99 "cd /opt/ara && venv/bin/python -c 'import py_compile; py_compile.compile(\"server.py\", doraise=True); print(\"Syntax OK\")'"
ssh root@46.224.132.99 "systemctl kill ara-server && sleep 2 && systemctl start ara-server && sleep 6 && systemctl is-active ara-server"
```

Gate tests run AFTER the server restarts to verify live behavior.

## Known Infrastructure Issues

- When `ssh()` in Python returns empty for DB queries, run them directly: `ssh root@46.224.132.99 "cd /opt/ara && python3 -c '...'"` — the Python→SSH→Python chain sometimes drops output.
- SyntaxWarning about `\|` in f-strings: use raw strings or escape properly.
- `EADDRINUSE` on sidecar `require()` is expected — sidecar is already running on port 8767.
