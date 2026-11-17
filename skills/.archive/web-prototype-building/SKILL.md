---
name: web-prototype-building
description: "Build full-stack web application prototypes with FastAPI + SQLite + Tailwind CSS + HTML. Covers project scaffolding, server lifecycle, crash recovery, and the 'build fast, iterate on user feedback' loop."
version: 1.6.0
author: Hermes Agent via Johnny
metadata:
  hermes:
    tags: [fastapi, sqlite, tailwind, prototype, web, full-stack]
---

# Web Prototype Building

Build working full-stack web prototypes quickly — FastAPI backend, SQLite database, HTML templates with Tailwind CSS. This is a class-level skill for the pattern: user gives a product idea -> you build a working localhost server -> user tests it -> you iterate.

This skill covers the **HOW** of building web prototypes. For guidance on *what* to build (product vision interrogation, spec-construction), load `user-interaction-style` instead.

## Trigger Conditions

Load this skill when:
- The user says "build it" or "let's go" after a product spec session
- You need to build a working web server to demonstrate a product concept
- You're setting up FastAPI + SQLite + HTML pages
- A server crashed and needs recovery
- The user wants UI changes (make it tabbed, add animations, etc.)
- Building LLM-powered form previews (cadence steps, email drafts, call scripts)
- Designing per-template multi-config state (multiple named configs with switching + unsaved-changes prompt)

## Architecture Pattern

```
/Users/greg/<project-name>/
├── server.py              # FastAPI app — all routes + HTML in one file for speed
├── database.py            # SQLAlchemy ORM models + init_db()
├── <module>_engine.py     # Business logic modules (induction, sdr, etc.)
├── <module>_template.py   # Large HTML template strings in separate file
└── venv/                  # Python virtual environment
```

### Why one-file server.py for prototypes
- Faster to build and iterate — no imports across 5 files
- The user tests immediately, finds issues, you fix in one place
- Split into modules only when the file exceeds ~600 lines

### ⚠️ CRITICAL: HTML goes in Python strings, JS NEVER does

**HTML in Python strings:** Fine. No escaping issues — HTML entities (`&lt;`, `&amp;`) are just text. Use Jinja2 later if needed, but f-strings work for V1.

**JavaScript in Python strings: NEVER.** Python's `"""..."""` (triple-quoted) strings consume backslash escapes before JS ever sees them. `\\'` becomes just `'` and breaks your JS. Even if you master the escaping (double-backslash-chasing), you create a maintenance liability — every future edit risks the same bug.

**Rule: JavaScript goes in `static/` files, period.**
```
/Users/greg/<project-name>/
├── server.py              # FastAPI app
├── static/
│   ├── dashboard.js       # All JS — no inline <script> blocks
│   └── style.css          # Optional: CSS extracted for large stylesheets
└── database.py            # SQLAlchemy ORM
```

**When you MUST inline JS (throwaway simulators/mockups), the `""+var+""` pattern is a silent killer.** Inside a Python triple-quoted string, `"<b>"+tag+"</b>"` produces valid-looking bytes but the two consecutive double-quotes (`22 22` in hex) become a JS string terminator. The generated JS sees `"<b>"` (complete string), then `"` (opens new empty string), then `+tag+` (literal text inside the new string), then `"` (closes it), then `</b>` (unquoted → SyntaxError). `node --check` catches this immediately; the browser falls silent with zero console output.

**Fix:** Use single quotes for the concatenation boundary: `'<b>'+tag+'</b>'`. Single quotes don't collide with the outer double-quoted JS string. Always verify with `node --check` on the extracted `<script>` block before opening the HTML file.

**Byte-level diagnosis pattern:** When `node --check` says "Unexpected string" at a line that looks fine, inspect raw bytes:
```bash
sed -n '<LINE>p' /tmp/file.html | xxd
```
Look for consecutive `22 22` (double-quote, double-quote) where there should be `22 2b` (double-quote, plus). This pattern is specific to `execute_code` generating HTML — the Python string layer preserves double-quotes but the JS parser sees them as terminators.

**How to serve (server.py):**
```python
from fastapi.staticfiles import StaticFiles
from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
```

**How to include (HTML template):**
```html
<script src="/static/dashboard.js"></script>
```

**Zero escaping bugs. Zero syntax errors. Zero triple-backslash nightmares.**

The HTML template can still use Python f-strings and inline CSS — those have no escaping collision with Python strings. Only JS extraction is strictly enforced.

### Database Pattern
- SQLite + SQLAlchemy ORM (aiosqlite optional — use sync for simplicity)
- Multi-tenant with `tenant_id` column scoping on every table
- Use `init_db()` returning a Session, reuse via FastAPI `Depends(get_db)`
- Schema: tenants, skills, leads, conversations, coaching_logs

#### Adding Columns to Existing Models (Auto-Migration)

When adding a new column to an existing SQLAlchemy model in a prototype that already has a populated database, use ALTER TABLE as a fallback in `init_db()`. This handles both fresh installs (the new column is created automatically by `Base.metadata.create_all()`) and existing databases (the column is added via raw SQL):

```python
def init_db():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)

    # Auto-migrate: add new columns to existing tables
    conn = engine.connect()
    try:
        # Check if column exists (SQLite doesn't support IF NOT EXISTS for ALTER TABLE)
        columns = [row[1] for row in conn.execute("PRAGMA table_info(documents)").fetchall()]
        if "source" not in columns:
            conn.execute("ALTER TABLE documents ADD COLUMN source VARCHAR DEFAULT 'kb'")
    except Exception:
        pass  # Table may not exist yet on first run
    finally:
        conn.close()

    return engine
```

**Key points:**
- `Base.metadata.create_all()` handles fresh installs — it creates ALL columns from the model definition
- The ALTER TABLE only runs if the column is missing, so it's safe to run every startup
- Use `PRAGMA table_info(table_name)` to check column existence (SQLite-specific)
- Set a sensible DEFAULT for existing rows
- This pattern works for SQLite; for PostgreSQL use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
- Apply this pattern to EVERY new column addition, not just the first one — the first user with a populated DB will hit a crash otherwise

**Pain point avoided:** Without this, existing databases crash on first query with `sqlalchemy.exc.OperationalError: no such column`. The user has to manually delete the DB file or run raw SQL. This auto-migration makes prototype iterations seamless.

### UI Pattern
- Tailwind CSS via CDN: `<script src="https://cdn.tailwindcss.com"></script>`
- Render HTML as Python f-strings in the FastAPI endpoint
- For large templates (>100 lines), extract to a separate `_template.py` file
- Default to light theme (#f8fafc bg) unless user says otherwise
- **Animations matter** — add skill-save toasts (like Hermes tool logs), typing indicators (three bouncing dots), progress bars that animate, module completion confetti. These aren't "nice to haves" — they're what makes the prototype feel alive. Greg's feedback: "Make the fancy animation to say it's registering and saving it within its skills like the Hermes tool call / process log."
- **Tabbed layout for multi-section flows** — When the UI has multiple sections (induction modules, settings panels), use tabs within a single page, not continuous scroll. Allow the user to switch between tabs and see progress per tab. Keep the chat/input always at the bottom of the active tab.

## Server Lifecycle

### Starting
```python
# In terminal (background), pass env vars explicitly:
cd /Users/greg/ara && DEEPSEEK_API_KEY="sk-..." /path/to/venv/bin/python -u server.py
```

```python
# Background with notify_on_complete so you get notified on crash:
terminal(background=True, notify_on_complete=True, command="...")
```

### Verifying (after start)
```bash
sleep 3 && curl -s -o /dev/null -w "%{http_code}" http://localhost:8766/
```

### Stopping
```python
process(action="kill", session_id="proc_xxx")
```

### Restarting (after code changes)
1. Kill old server (find session_id via process list if needed)
2. Wait 1-2 seconds
3. Start new server with same command

### Pitfall: Server starts silently
The server might start without printing "Starting ARA Server..." if stdout is buffered. Use `python -u` for unbuffered output. If curl gets connection refused after `sleep 3`, check the process is still running with `process(action="poll")`.

### Pitfall: `env` prefix vs bare `VAR=value` in background commands
When passing environment variables to background processes, the `env` prefix is more reliable than bare `VAR=value`:

```bash
# MORE RELIABLE — env prefix propagates correctly through the shell wrapper
env DEEPSEEK_API_KEY="sk-..." /path/to/venv/bin/python -u server.py

# LESS RELIABLE — may not propagate via the background shell wrapper
DEEPSEEK_API_KEY="sk-..." /path/to/venv/bin/python -u server.py
```

The background terminal tool wraps the command in `bash -lic` which can strip bare env var prefixes. Use `env VAR=value ...` to guarantee propagation. Always verify with a test curl after starting.

### Dependency Pre-Flight Check

Before starting the server, verify ALL critical imports resolve in the target Python interpretter — don't assume one working import means everything is fine:

```bash
# Run this in the project directory before starting:
/path/to/venv/bin/python3.11 -c "
import fastapi, uvicorn, sqlalchemy, pydantic, dotenv, httpx
import database, induction_engine, email_utils
print('Dependencies OK')
"
```

If this fails, the exact missing package is shown — install with pip before proceeding:

```bash
/path/to/venv/bin/python3.11 -m pip install <missing-package>
```

**Common gap:** `fastapi` and `uvicorn` may be installed while `sqlalchemy` is not (they're independent packages). Also check `pydantic`, `python-multipart`, `httpx`, `python-dotenv`. These don't always come bundled.

### Server Startup Diagnostics

When the server fails to start silently:

1. **Check `process(action="log")` first** — the background process captured stderr/stdout which shows the Python traceback
2. Don't blindly restart — read the error, fix the root cause
3. Common silent failures: missing imports, port in use, syntax errors from a recent `write_file` overwrite

```python
# After starting background process:
process(action="log", session_id="proc_xxx")  # Read the full output
process(action="poll", session_id="proc_xxx")  # Check if still running
```

If `process(action="log")` shows the server started but output is empty, it's either still initializing (wait 3-5s) or stdout is buffered (always use `python -u` for unbuffered output).

### Crash Recovery Pattern

#### Launcher Script (Auto-Restart)

For background servers that should survive crashes, use a bash launcher with a restart loop:

```bash
#!/bin/bash
# launcher.sh — auto-restarts on crash
export DEEPSEEK_API_KEY="sk-..."
cd /Users/greg/ara
while true; do
    echo "[$(date)] Starting server..."
    /path/to/venv/bin/python -u server.py 2>&1
    EXIT_CODE=$?
    echo "[$(date)] Server exited with code $EXIT_CODE. Restarting in 2s..."
    sleep 2
done
```

Start with `terminal(background=True, command="/path/to/launch_ara.sh")`. The process notifies on exit (exit 0 = clean stop, other = crash + restart).

#### Cleaning Up Zombie Processes

When background processes accumulate from multiple restarts (context compression loses the session_id reference), clean up before starting fresh:

```bash
lsof -ti:8766 | xargs kill -9 2>/dev/null
sleep 2
lsof -ti:8766 2>/dev/null || echo "Port clear"
```

**Never start a new server without verifying the old one is dead** — the bind will fail silently and the old zombie continues serving stale code.

#### Recovery From Accidental write_file

If you accidentally corrupt server.py (e.g., `write_file` overwrites the entire file instead of patching it):

1. **Don't panic** — you know the architecture well enough to rebuild
2. **Re-read any surviving files** — database.py, engine files, templates survive
3. **Rebuild server.py from scratch** — include ALL endpoints: tenant CRUD, leads, skills, conversations, coaching, dashboard, induction chat
4. **Check the imports match** — make sure all module references (database, engines, templates) are correct
5. **Verify with curl** after restart

### Zapping Old Processes When pkill/pgrep Times Out

Sometimes `pkill -9 -f server.py` or `kill -9` on port 8766 hangs or times out in the terminal tool. This happens when there are too many zombie processes for the shell to terminate atomically. Workaround:

1. Try `lsof -ti:8766` first to get a single PID
2. If that shows a PID, `kill -9 <pid>` with a short timeout (5s)
3. If `lsof -ti` times out, the terminal is stuck — move to a *new* terminal call with `command="true"` (no-op) to reset the terminal state, then retry `lsof`
4. If all else fails, `pkill -9 -f server.py` with user approval

### Prevention
- Use `patch()` for targeted edits on existing files — never `write_file` for partial file updates
- `write_file` OVERWRITES the entire file; it doesn't "write starting at a line"
- Read the full file first with `read_file` before deciding on the edit strategy
- Use `search_files` to find function boundaries before patching

### Route Swapping (New UI Replaces Old)

When moving a new dashboard/UI onto the main route (e.g., `/dashboard`):

1. Add the new route under a temporary name: `@app.get("/dashboard-v2")`
2. Rename the old route: `@app.get("/dashboard")` -> `@app.get("/dashboard-old")`
3. Move the new route: `@app.get("/dashboard-v2")` -> `@app.get("/dashboard")`
4. Update any redirects or nav links that pointed to the old route
5. Verify old links still work (some may still reference `/dashboard`)

## Induction Engine Architecture (for product onboarding)

When building a conversational onboarding/induction flow:

### System Prompt Design
1. **Instructions for the LLM must be extremely explicit** — LLMs ignore subtle formatting. Use block delimiters like `===SAVE_SKILL===` that are visually impossible to skip.
2. **Module completion detection**: Require the LLM to emit `MODULE COMPLETE: Proposition` as a signal. Parse this with regex in the backend.
3. **Scoring**: Never trust the LLM's self-reported score alone. Verify actual persisted data (skills saved per module) before marking modules complete.
4. **Strict scoring rubric**: If the user's answers are thin or surface-level, score in the 30-50 range and explain what's missing. Don't give 90/100 for vague answers — that trains the user to be lazy. The LLM should proactively ask specific follow-up questions when information is insufficient.
5. **No module completion without persisted skills**: A module is NOT complete just because the LLM says it is. Must have at least 2 saved skills in the DB for that module's category. Validate against the database, not against the LLM's self-report.

#### Induction Session Lifecycle
- `INDUCTION_SESSIONS` is an in-memory dict (tenant_id -> message list). It's ephemeral — lost on server restart.
- **When the induction engine or system prompt changes, clear the old session**: delete from `INDUCTION_SESSIONS`, and delete old `CoachingLog` entries where `feedback_type='induction'` for that tenant. Otherwise the user's old conversation bleeds into the new engine.
- To clear: `db.query(CoachingLog).filter(CoachingLog.tenant_id == X, CoachingLog.feedback_type == 'induction').delete()` then `db.commit()`.
- The first POST to `/api/induction/{tenant_id}/chat` creates a fresh session with the current system prompt. No manual session initialization needed.

## Skill Extraction
```python
# Regex pattern to extract skills from LLM response:
pattern = r'===SAVE_SKILL===\s*(\{.*?\})\s*===END_SAVE_SKILL==='
matches = re.findall(pattern, response_text, re.DOTALL)
```

### State Tracking
- Keep an `INDUCTION_SESSIONS` dict (tenant_id -> message list) in memory
- Persist skills to DB immediately on each response
- Derive module coverage from DB queries, not from LLM state

See [ARA Product Design Reference](references/ara-product-design.md) for the full product specification.

## Service Architecture
- Run on port 8766 (consistent convention — avoids port conflicts with other services)
- See [ARA Dependency Profile](references/ara-dependency-profile.md) for the full Python venv, pip packages, and server layout
- Single-tenant by default for prototype; multi-tenant DB schema under the hood
- Root URL (`/`) redirects to the core interaction page
- `/dashboard` shows full metrics with knowledge base breakdown

## User-Facing Error Messages — Never Expose Internals

**Hard rule:** All error messages shown to the user in the web UI MUST be clean, user-facing language. Never include:

- Provider names (`DEEPSEEK`, `OpenAI`, `Claude`)
- API key names (`API_KEY`, `api_key`, credentials)
- HTTP status codes (`401`, `500`)
- Stack traces, exception messages, or technical details
- Internal config keys (`enabled_toolsets`, `fallback_providers`)

Instead, use one of these patterns depending on context:

| Situation | User-Facing Message |
|---|---|
| Service unavailable | "I'm sorry — the service is temporarily unavailable. Please try again in a moment." |
| Timeout | "The service is taking longer than expected. Please try again." |
| Generic failure | "I encountered an issue processing your request. Please try again." |
| Invalid input | Be specific about what the user did wrong (e.g., "Please enter a valid email address.") |

The **only** exception is the terminal/server log output, which is internal. Everything rendered in an HTML page, dashboard, or chat bubble must pass this filter.

**Implementation pattern:**

```python
# In engine files — catch at the top level, return user-safe strings
except httpx.TimeoutException:
    return "The service is taking longer than expected. Please try again."
except Exception:
    return "I encountered an issue processing your request. Please try again."
```

## Induction Template Asset

The full induction chat UI (tabbed layout, skill-save toasts, module cards, confetti celebrations) is saved as a standalone HTML template. Reference it rather than rebuilding:

- Location: `induction_template.py` in the project directory
- Contains: tabbed sidebar with 5 tabs (Overview + 4 modules), conversation panel with typing indicators, skill-toast overlay, module progress bars, confetti celebration, induction completion screen
- Variable substitution: `{{TENANT_ID}}` and `{{COMPANY}}` are replaced at render time
- Import via: `from induction_template import INDUCTION_CHAT_HTML`

See the [ARA Induction UI reference](references/ara-induction-ui.md) for the full template.

## QA Verification (mandatory before release)

After any build or change, load the **ara-qa-checklist** skill and run through it before declaring done. See also the [ARA Build Session Reference](references/ara-prototype-build-may2026.md) for the full debugging story and lessons from this session.

## State-Dependent UI Pattern (critical for UX continuity)

When a prototype involves a multi-step conversational flow (like induction), the UI must gracefully handle server restarts WITHOUT requiring the user to start over:

### 1. Button Text Must Reflect State
- **Before any skills exist**: "Start Induction ->"
- **After skills exist**: "Continue Induction ->"
- Implementation: check `state.skill_count > 0` in `updateUI()` and set button text dynamically
- Dont hardcode this in HTML — it MUST be set by the loaded state

### 2. Module Navigation Must Route Correctly
- Clicking "Continue" must open the FIRST incomplete module, not always Module 1
- Find the first module where `covered === false` in the loaded state
- If all modules are covered, open the overview/complete screen

### 3. Welcome Message Must Be Dynamic
- **Generic "send your first answer" is bad UX** — it leaves the user wondering what to do
- Show a **module-specific starting question** that matches the current module:
  - GTM Learnings: "What channels and strategies have worked best? What has NOT worked?"
  - Inbound: "How do leads typically find you? Walk me through the inbound process."
  - Guardrails/Policies: "What rules must the agent follow? Pricing ranges, competitors?"
  - Any new module: "Tell me about your product and who you sell to."
- Count how many modules are already completed and say "You have completed X modules"

### 4. LLM System Prompt Must Match UI Routing
- The LLMs first response should align with what the UI shows
- If the UI opens to GTM Learnings, the system prompt must say "Start with Module 2: GTM Learnings"
- Never hardcode "Start Module 1: Proposition" — derive it from the DB state
- Implementation:
  ```python
  next_idx = min(skills_state['covered_count'], skills_state['total_modules'] - 1)
  next_module = skills_state['modules'][next_idx]
  ```

### 5. Skills Must Survive Server Restarts
- Skills/leads data goes in SQLite, not in-memory dicts
- In-memory `INDUCTION_SESSIONS` dict is ephemeral — reconstruct from DB on each new chat message
- On session creation: check DB for existing skills, include them in the system prompt so the LLM knows what it has already learned
- The state API endpoint (`/induction/chat/{id}/state`) must read from DB, not from memory

### Chat UI Text Input Pattern

For chat/messaging interfaces where users type multi-line responses:

- Use `<textarea>` not `<input type="text">` — textarea wraps naturally, input scrolls horizontally
- **Enter** sends (keydown: `if (e.key === 'Enter' && !e.shiftKey)`)
- **Shift+Enter** adds a newline
- **Auto-reset height** after send: `inp.style.height = 'auto';`
- **CSS:** `resize: none; overflow-y: auto; max-height: 180px; line-height: 1.5;`

```html
<textarea id="messageInput" placeholder="Type..." rows="1"
  onInput="this.style.height='auto';this.style.height=Math.min(this.scrollHeight, 180)+'px'"></textarea>
```

## URL Fetch Capability

When the agent chat needs to fetch and read a specific URL (case studies, LinkedIn profiles, competitor pages), use httpx + lxml:

```python
def fetch_url(url):
    try:
        import httpx
        from lxml import html
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        if resp.status_code != 200:
            return f"URL returned status {resp.status_code}"
        ct = resp.headers.get("content-type", "")
        if "text/html" in ct or "text/plain" in ct:
            tree = html.fromstring(resp.text.encode())
            # Remove scripts, styles, nav, footer, header
            for tag in tree.cssselect("script, style, nav, footer, header"):
                tag.getparent().remove(tag)
            body = tree.find(".//body") or tree
            text = body.text_content().strip()
            import re
            text = re.sub(r'\s+', ' ', text)
            return text[:4000]  # Cap at 4000 chars
        else:
            return f"Page content type: {ct}. First 1000 chars: {resp.text[:1000]}"
    except Exception as e:
        return f"Failed to fetch URL: {str(e)}"
```

System prompt marker:
```
[FETCH_URL: https://example.com/page]
```

## WhatsApp Web Automation via Playwright

For SDR outreach via a user's personal WhatsApp (linked devices approach — no Twilio/API costs):

### Architecture

```
server.py (FastAPI endpoint)
  └─ whatsapp_manager.py (Playwright controller)
       └─ Headless Chromium → web.whatsapp.com
            └─ Multi-device session (persisted via storage_state.json)
```

### Manager Pattern (Singleton + Async Wrapper)

```python
import os, base64, asyncio, threading
from playwright.async_api import async_playwright

SESSION_FILE = "~/.hermes/ara_whatsapp_session.json"

class WhatsAppManager:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self._ready = False
        self._loop = None

    def _ensure_loop(self):
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    # All public methods are sync wrappers that delegate to async implementations:
    def start_sync(self):
        return self._ensure_loop().run_until_complete(self._start())
    def get_qr_sync(self):
        return self._ensure_loop().run_until_complete(self._get_qr())
    def send_message_sync(self, number, text):
        return self._ensure_loop().run_until_complete(self._send_message(number, text))
    def status_sync(self):
        return self._ensure_loop().run_until_complete(self._status())

# Singleton
wa = WhatsAppManager()
```

### QR Authentication Flow

**Start:** Navigate to `https://web.whatsapp.com`, wait for canvas element (QR code), screenshot it, serve as base64.

**Session persistence:** After successful auth, save browser context storage state:
```python
await context.storage_state(path=SESSION_FILE)
```

**Restore:** On next start, load the saved state:
```python
if os.path.exists(SESSION_FILE):
    context = await browser.new_context(storage_state=SESSION_FILE)
```

### Send Message

```python
async def _send_message(self, number, text):
    phone = "".join(c for c in number if c.isdigit())
    encoded_text = urllib.parse.quote(text)
    url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_text}"
    await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
    await asyncio.sleep(3)
    send_btn = await self.page.wait_for_selector(
        'button[data-testid="compose-btn-send"], button[aria-label="Send"]',
        timeout=10000
    )
    if send_btn:
        await send_btn.click()
        await asyncio.sleep(1)
        await self.context.storage_state(path=SESSION_FILE)
        return {"success": True}
    return {"error": "Send button not found"}
```

### Key Details

- **User-Agent:** `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36` — WhatsApp Web detects bare UAs and may block
- **Multi-device:** WhatsApp Web now works independently of phone connectivity (since 2022)
- **Lazy start:** Start the browser on first `/api/whatsapp/link` visit, not on server boot
- **Thread safety:** Use `threading.Thread(target=wa.start_sync, daemon=True)` to start without blocking the FastAPI event loop
- **Headless mode:** `headless=True` works; no display needed on macOS
- **Playwright install:** `pip install playwright && python -m playwright install chromium` (downloads ~170MB Chromium)
- **Session survives server restarts** — the `storage_state.json` file persists

### Endpoints Pattern

```python
# QR link page — serves HTML page with QR + polling JS
@app.get("/api/whatsapp/link", response_class=HTMLResponse)

# QR code as base64
@app.get("/api/whatsapp/qr")

# Connection status
@app.get("/api/whatsapp/status")

# Send message
@app.post("/api/whatsapp/send")
```

### Premium/Enterprise Tier

For org-level usage (multi-number, higher volume, guaranteed deliverability), swap in Twilio WhatsApp Business API as a backend option. Same Ava interface, different transport:

```
Ava → [WHATSAPP: number | text]
       ├── Personal: Playwright → web.whatsapp.com (free, 20-50 msgs/day)
       └── Enterprise: Twilio API → WhatsApp Business (paid, production)
```

The marker syntax `[WHATSAPP: ...]` remains the same regardless of transport — the backend routes based on which is configured.

### Risks & Mitigations

| Risk | Likelihood at 20 msgs/day | Mitigation |
|------|---------------------------|------------|
| Account flagged for automation | Low | Warm-up period, human-like pacing, limit to ~50/day |
| Session expiry | Periodic | Auto-detect + notify user to re-scan QR |
| WhatsApp DOM changes | Every few months | Keep selectors in one place, easy to update |
| Chromium version drift | Low | `playwright install chromium` on upgrade |

### Critical Pitfall: storage_state() Doesn't Save IndexedDB

**Playwright's `storage_state()` does NOT capture IndexedDB** — and WhatsApp Web stores its auth tokens there. If the session is lost on restart, switch from `launch() + new_context(storage_state=file)` to `launch_persistent_context(user_data_dir=path)`. See [WhatsApp Session Persistence Reference](references/whatsapp-session-persistence.md) for the full implementation and debugging story.

## Free Web Search Integration (No API Key)

When the agent chat needs to search the web for company news, competitor intel, or market trends, use DuckDuckGo's HTML endpoint directly (free, no API key):

```python
def web_search(query, max_results=5):
    try:
        import httpx
        from lxml import html
        params = {"q": query}
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = httpx.get("https://html.duckduckgo.com/html/",
            params=params, headers=headers, timeout=10, follow_redirects=True)
        if resp.status_code != 200:
            return f"Search returned status {resp.status_code}"
        tree = html.fromstring(resp.text.encode())
        results = []
        for i, result in enumerate(tree.cssselect(".result")):
            if i >= max_results: break
            title_el = result.cssselect(".result__title a")
            snippet_el = result.cssselect(".result__snippet")
            if title_el:
                title = title_el[0].text_content().strip()
                href = title_el[0].get("href", "")
                snippet = snippet_el[0].text_content().strip() if snippet_el else ""
                results.append(f"- [{title}]({href})\n  {snippet[:300]}")
        return "\n\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Search failed: {str(e)}"
```

**Key points:**
- `cssselect` requires `pip install cssselect` (not always bundled with lxml)
- **DO NOT use the `ddgs` or `duckduckgo_search` PyPI packages** — they route through Mojeek (different engine) which may be blocked on the server's network
- The simpler the User-Agent, the better: `"Mozilla/5.0"` works; the full UA string can trigger 202 rate-limiting
- `follow_redirects=True` is essential — DuckDuckGo may redirect the request

### Multi-Tool Agent Dispatch (Two-Stage LLM Loop)

When the agent chat has multiple tools (SEARCH, FETCH_URL, WHATSAPP), use a single two-stage loop that checks for ALL markers:

```python
import re
search_match = re.search(r'\[SEARCH:\s*(.*?)\]', response)
url_match = re.search(r'\[FETCH_URL:\s*(.*?)\]', response)
wa_match = re.search(r'\[WHATSAPP:\s*(.*?)\s*\|\s*(.*?)\]', response)

if search_match or url_match or wa_match:
    # Determine which tool to call
    if search_match:
        query = search_match.group(1).strip()
        response_clean = re.sub(r'\[SEARCH:\s*.*?\]', '', response).strip()
        tool_result = web_search(query)
        tool_label = f"Web search results for '{query}'"
    elif url_match:
        url = url_match.group(1).strip()
        response_clean = re.sub(r'\[FETCH_URL:\s*.*?\]', '', response).strip()
        tool_result = fetch_url(url)
        tool_label = f"Content from {url}"
    else:
        wa_number = wa_match.group(1).strip()
        wa_text = wa_match.group(2).strip()
        response_clean = re.sub(r'\[WHATSAPP:\s*.*?\s*\|\s*.*?\]', '', response).strip()
        wa_result = wa.send_message_sync(wa_number, wa_text)
        if wa_result.get("success"):
            tool_result = f"Message sent to {wa_number}"
        else:
            tool_result = f"Failed: {wa_result.get('error', 'unknown error')}"
        tool_label = "WhatsApp Result"

    # Stage 2: Re-call LLM with tool results
    tool_context = f"{tool_label}:\n{tool_result}\n\nBased on this, respond to the user."
    messages.append({"role": "assistant", "content": response_clean})
    messages.append({"role": "user", "content": tool_context})
    response = call_llm(messages)
```

The system prompt should describe each tool marker clearly. Markers are `[...]` brackets with a keyword prefix:

- `[SEARCH: query]` — web search
- `[FETCH_URL: url]` — read a page
- `[WHATSAPP: number | text]` — send WhatsApp message

The `|` separator for WHATSAPP means the regex must handle `\s*\|\s*` (whitespace-pipe-whitespace). Test regex carefully for each marker format.

### Agent Chat System Prompt

The system prompt for the revenue agent should include:

## Agent Chat with Real-Time DB Context (Class-Level Pattern)

When adding an AI chat panel to a CRM/dashboard prototype, the agent needs live data about the pipeline. **Conversation history MUST survive server restarts** — use a dedicated DB table, not an in-memory dict.

### Database Model

Add a table in `database.py` dedicated to agent chat messages:

```python
class AgentChatMessage(Base):
    """Persistent chat history for the AI agent conversation."""
    __tablename__ = "agent_chat_messages"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)
```

The table auto-creates on server restart via `Base.metadata.create_all(engine)` in `init_db()` — no migration script needed.

### Backend Endpoint — DB-Backed Pattern

```python
AGENT_SYSTEM_PROMPT = """..."""  # same as below

@app.post("/api/agent/chat/{tenant_id}")
def agent_chat(tenant_id: str, data: dict, db: DBSession = Depends(get_db)):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not t:
        raise HTTPException(404)

    user_msg = data.get("message", "").strip()
    if not user_msg:
        return {"response": "Please say something!"}

    # Build context from DB — fresh on every request
    leads = db.query(Lead).filter(Lead.tenant_id == tenant_id).all()
    skills = db.query(Skill).filter(Skill.tenant_id == tenant_id).all()
    docs = db.query(Document).filter(Document.tenant_id == tenant_id).all()

    lead_details = "\n".join([...]) if leads else "No leads yet."
    skills_context = "\n".join([...]) if skills else "No knowledge yet."
    doc_context = "\n".join([...]) if docs else "No docs uploaded."

    system_prompt = AGENT_SYSTEM_PROMPT.format(...)

    # Load persistent conversation history from DB (last 20 turns)
    recent_msgs = db.query(AgentChatMessage).filter(
        AgentChatMessage.tenant_id == tenant_id
    ).order_by(AgentChatMessage.created_at.asc()).limit(20).all()

    messages = [{"role": "system", "content": system_prompt}]
    for m in recent_msgs:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": user_msg})

    response = call_llm(messages)

    # Save both turns to DB for persistent memory
    db.add(AgentChatMessage(tenant_id=tenant_id, role="user", content=user_msg))
    db.add(AgentChatMessage(tenant_id=tenant_id, role="assistant", content=response))
    db.commit()

    return {"response": response}
```

### Why a dedicated table (not reusing CoachingLog or Conversation)

| Approach | Problem |
|----------|---------|
| In-memory dict (`AGENT_CHAT_SESSIONS`) | **Lost on server restart.** User comes back to a blank chat. |
| Reusing `CoachingLog` with `feedback_type='agent_chat'` | Works, but pollutes coaching data. The agent chat has mixed user/assistant messages, tool call markers, and potentially different query patterns. A dedicated table keeps things clean and queryable. |
| Dedicated `AgentChatMessage` table | **Correct.** Clear schema, fast queries, survives restarts, no side effects. |

### Key Points
- Query the DB fresh on each request — the system prompt is always current with live pipeline data
- `order_by(created_at.asc()).limit(20)` loads the last 20 turns (10 exchanges) in chronological order
- The `call_llm` function should come from a shared module (e.g. `induction_engine.py`)
- For the `[SEARCH]`/`[FETCH_URL]`/`[WHATSAPP]` tool dispatch, see the "Multi-Tool Agent Dispatch" section below
- The old pattern (in-memory `AGENT_CHAT_SESSIONS = {}`) is **deprecated** — always use DB-backed persistence

### Frontend Wiring

```javascript
function addChatMsg(text, isUser) { /* append bubble to #chatMessages */ }
function showTyping() { /* append "Ava is thinking..." indicator */ }
function hideTyping() { /* remove indicator */ }

async function sendChatMsg(text) {
    showTyping();
    var r = await fetch('/api/agent/chat/' + TENANT, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: text})
    });
    var data = await r.json();
    hideTyping();
    addChatMsg(data.response, false);
}

// Wire up suggestion chips and input
document.querySelectorAll('.chat-suggestion').forEach(function(el) {
    el.addEventListener('click', function() { sendChatMsg(el.textContent.trim()); });
});
document.getElementById('chatInput').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') sendChatMsg(this.value);
});
```

### Key Points
- Query the DB fresh on each request — the system prompt is always current
- Maintain conversation history in memory (last ~20 turns) for context
- The LLM should NOT make up data — only reference what is in the `lead_details` section
- For the `call_llm` function, reuse the existing one from `induction_engine.py` (same API key, same model)
- **Pitfall — messages appearing twice in chat**: When both `sendMsg()` (button/Enter handler) and `sendChatMsg()` (send function) call `addChatMsg(text, true)`, the message gets added twice. Fix: only `sendChatMsg()` adds the message. `sendMsg()` should clear the input and call `sendChatMsg()` — nothing else:
  ```javascript
  // WRONG — adds message twice
  function sendMsg() {
    addChatMsg(text, true);  // added here
    sendChatMsg(text);       // AND added here again
  }

  // RIGHT — sendChatMsg handles all message addition
  function sendMsg() {
    sendChatMsg(text);  // sendChatMsg calls addChatMsg internally
  }
  ```

## Dashboard CRM UI Reference

The dashboard-v2 build in May 2026 produced a premium CRM-style UI with sidebar navigation, stats grid, lead detail page, chat panel, and event delegation. See `references/dashboard-v2-crm-ui.md` for full architecture, color palette, and JavaScript patterns.

## Catalog-Driven Integrations UI

For settings/configurations dashboards where each item has a connect/disconnect toggle, use the catalog-driven pattern:

1. **Backend catalog** — Define a static `INTEGRATIONS_CATALOG` list in `server.py` with id, name, description, icon, category, and coming_soon flag
2. **Live status check** — `_get_integration_status(id)` checks runtime state per integration (Playwright connection, env vars, etc.)
3. **Unified GET endpoint** — `/api/integrations` merges catalog + live statuses
4. **Action endpoints** — `POST /api/integrations/{id}/connect` and `/disconnect` handle each integration's lifecycle
5. **Dynamic frontend** — `renderIntCards()` fetches from API, filters by search query + category pill, renders cards grouped by category
6. **CSS-only toggle switch** — Checkbox hack with `input:checked + .toggle-slider::before` for the sliding knob
6. **Auto-polling** — `setInterval` every 5s refreshes status without full page reload
7. **Card-body click delegation** — clicking anywhere on the card (icon, name, description) toggles the integration via a delegated listener on the parent container. See `references/integrations-catalog-ui.md` for the implementation.

**See full implementation:** `references/integrations-catalog-ui.md`

### Why this pattern works for prototypes
- Adding a new integration = adding one catalog entry + one status checker function
- No frontend changes needed for a new entry — the API delivers all data
- The toggle/badge/search/category logic is generic and handles any catalog shape
- Coming Soon items are greyed out with disabled toggles — communicates roadmap without building

## Conversation Persistence (Surviving Server Restarts)

When a prototype involves a conversational AI flow (like induction, coaching, or onboarding), **the in-memory conversation dict is ephemeral** — lost on server restart. This causes the agent to forget where the user left off.

### Architecture

**PERSIST every user message and assistant response to the database.**

Two approaches:

### Approach A: Reuse CoachingLog (good for induction/training where messages are already linked to coaching)
Uses three `feedback_type` values in the `CoachingLog` table:
- `"induction_chat"` — user message
- `"induction_chat_response"` — assistant/LLM response

**On session creation** (user sends first message after restart):

```python
if tenant_id not in SESSIONS:
    # 1. Gather existing skills from DB -> inject into system prompt
    skills = db.query(Skill).filter(Skill.tenant_id == X).all()
    skills_context = ""
    if skills:
        skills_context = "Existing knowledge:\n"
        for s in skills:
            skills_context += f"- [{s.category}] {s.key}: {s.value[:200]}\n"

    # 2. Reload last conversation turns from DB
    recent_logs = db.query(CoachingLog).filter(
        CoachingLog.tenant_id == X,
        CoachingLog.feedback_type.in_(["induction_chat", "induction_chat_response"])
    ).order_by(CoachingLog.id.desc()).limit(8).all()
    recent_logs.reverse()

    # 3. Build messages with system prompt + replay
    system_prompt = BASE_SYSTEM_PROMPT + f"""
Current state:
- Skills saved: {skills_state['skill_count']}
{skills_context}
{module_instruction}
"""
    messages = [{"role": "system", "content": system_prompt}]

    # 4. Replay conversation so the LLM knows what was discussed
    for log in recent_logs:
        if log.feedback_type == "induction_chat_response":
            messages.append({"role": "assistant", "content": log.feedback})
        else:
            messages.append({"role": "user", "content": log.feedback})

    SESSIONS[tenant_id] = messages
```

**On each turn:**

```python
# Save user message
db.add(CoachingLog(tenant_id=X, feedback_type="induction_chat", feedback=user_msg))
db.commit()

# Call LLM
response = call_llm(SESSIONS[tenant_id])

# Save assistant response
db.add(CoachingLog(tenant_id=X, feedback_type="induction_chat_response", feedback=response))
db.commit()

SESSIONS[tenant_id].append({"role": "assistant", "content": response})
```

**Key points:**
- Keep the last ~8 log entries (4 conversation turns) — enough context without bloating the prompt
- Reverse the query results so oldest is first (chronological order)
- Always include the existing skills context so the LLM knows what has already been covered
- The state API reads from the Skill table, not from memory — survives restarts
- The chat API creates fresh sessions on restart using DB data

This pattern applies to ANY conversational AI flow (induction, coaching, training, interviewing) — not just this specific prototype.

### Approach B: Dedicated AgentChatMessage Table (preferred for general agent chat)

For agent/revenue chat where you want clean separation from coaching data, use a dedicated table instead of CoachingLog:

```python
class AgentChatMessage(Base):
    __tablename__ = "agent_chat_messages"
    id = Column(String, primary_key=True, ...)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)
```

**Usage:** See the "Agent Chat with Real-Time DB Context" section above for the full endpoint pattern.

**When to use which:**
- **CoachingLog** — when messages are part of a coaching/induction workflow (skills extracted from conversation)
- **AgentChatMessage** — when the chat is general-purpose agent interaction (lead management, Q&A, pipeline review)

### Conversation Threads (Grouping Chats)

For ChatGPT-style thread organization of agent conversations, add a `ChatThread` table that groups `AgentChatMessage` records:

```python
class ChatThread(Base):
    __tablename__ = "chat_threads"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    title = Column(String, nullable=False, default="New Thread")
    thread_type = Column(String, default="general")  # "general" | "coaching" | "lead"
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
```

Add a `thread_id` column to `AgentChatMessage`:

```python
class AgentChatMessage(Base):
    __tablename__ = "agent_chat_messages"
    ...
    thread_id = Column(String, ForeignKey("chat_threads.id"), nullable=True, index=True)
```

#### Thread CRUD API Pattern

```python
# List all threads for a tenant (with last message preview)
@app.get("/api/threads/{tenant_id}")
def list_threads(tenant_id, db: DBSession = Depends(get_db)):
    threads = db.query(ChatThread).filter(
        ChatThread.tenant_id == tenant_id
    ).order_by(ChatThread.updated_at.desc()).limit(50).all()
    result = []
    for t in threads:
        last_msg = db.query(AgentChatMessage).filter(
            AgentChatMessage.thread_id == t.id
        ).order_by(AgentChatMessage.created_at.desc()).first()
        msg_count = db.query(AgentChatMessage).filter(
            AgentChatMessage.thread_id == t.id
        ).count()
        result.append({
            "id": t.id, "title": t.title, "type": t.thread_type,
            "last_message": last_msg.content[:80] if last_msg else "",
            "message_count": msg_count,
            "updated_at": t.updated_at.isoformat()
        })
    return result

# Create a new thread
@app.post("/api/threads/{tenant_id}")
def create_thread(tenant_id, data: dict, db: DBSession = Depends(get_db)):
    thread = ChatThread(
        tenant_id=tenant_id,
        title=data.get("title", "New Thread"),
        thread_type=data.get("type", "general"),
        lead_id=data.get("lead_id")
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return {"id": thread.id, "title": thread.title}

# Get thread with messages
@app.get("/api/threads/{tenant_id}/{thread_id}")
def get_thread(tenant_id, thread_id, db: DBSession = Depends(get_db)):
    thread = db.query(ChatThread).filter(
        ChatThread.id == thread_id, ChatThread.tenant_id == tenant_id
    ).first()
    if not thread:
        raise HTTPException(404)
    messages = db.query(AgentChatMessage).filter(
        AgentChatMessage.thread_id == thread_id
    ).order_by(AgentChatMessage.created_at.asc()).all()
    return {"thread": {"id": thread.id, "title": thread.title, ...}, "messages": [...]}

# Rename thread
@app.patch("/api/threads/{tenant_id}/{thread_id}")
def patch_thread(tenant_id, thread_id, data: dict, db: DBSession = Depends(get_db)):
    thread = db.query(ChatThread).filter(...).first()
    if data.get("title"): thread.title = data["title"]
    if data.get("type"): thread.thread_type = data["type"]
    db.commit()
    return {"success": True}

# Delete thread (cascade messages)
@app.delete("/api/threads/{tenant_id}/{thread_id}")
def delete_thread(tenant_id, thread_id, db: DBSession = Depends(get_db)):
    thread = db.query(ChatThread).filter(...).first()
    db.query(AgentChatMessage).filter(
        AgentChatMessage.thread_id == thread_id
    ).delete()
    db.delete(thread)
    db.commit()
    return {"success": True}
```

#### Thread-Scoped Agent Chat

When the agent chat endpoint receives a `thread_id`, scope the conversation history to that thread:

```python
@app.post("/api/agent/chat/{tenant_id}")
def agent_chat(tenant_id, data: dict, db: DBSession = Depends(get_db)):
    user_msg = data.get("message", "").strip()
    thread_id = data.get("thread_id")  # optional — None means unthreaded

    # Load history scoped to thread (or unthreaded messages)
    query = db.query(AgentChatMessage).filter(
        AgentChatMessage.tenant_id == tenant_id
    )
    if thread_id:
        query = query.filter(AgentChatMessage.thread_id == thread_id)
    else:
        query = query.filter(AgentChatMessage.thread_id == None)
    recent_msgs = query.order_by(AgentChatMessage.created_at.asc()).limit(20).all()

    # ... call LLM ...

    # Save with thread_id
    db.add(AgentChatMessage(tenant_id=tenant_id, role="user",
           content=user_msg, thread_id=thread_id))
    db.add(AgentChatMessage(tenant_id=tenant_id, role="assistant",
           content=response, thread_id=thread_id))
    db.commit()
```

#### Threads Frontend (ChatGPT-Style)

The `/threads` page is a separate full-page app with:
- **Left sidebar**: list of threads with title, preview, message count
- **Main panel**: chat window for selected thread (load on click)
- **New Thread button**: creates empty thread, opens blank chat
- **Delete**: removes thread + all messages
- **Auto-scroll**: `scrollTop = scrollHeight` on new messages

The nav bar links to `/threads` from the main dashboard sidebar.

**Full implementation:** `references/conversation-threads-with-whatsapp.md` — complete reference with schema, API routes, callback wiring, and frontend patterns from the ARA build.

### WhatsApp Conversation Logging to Leads

When WhatsApp messages (inbound or outbound) need to be tied to lead records, log them to the `Conversation` table using phone-based matching:

```python
def log_whatsapp_to_lead(db, phone, message, inbound=True, lead_id=None):
    """Log a WhatsApp message to the matching lead's conversation timeline."""
    if not lead_id:
        # Match by phone (last 10 digits)
        clean = "".join(c for c in phone if c.isdigit())[-10:] if phone else ""
        if not clean:
            return None
        lead = db.query(Lead).filter(Lead.phone.contains(clean)).first()
        if not lead:
            lead = Lead(tenant_id=TENANT_ID, name=f"WhatsApp {clean[-4:]}",
                       phone=clean, source="whatsapp_inbound", status="new")
            db.add(lead)
            db.commit()
            db.refresh(lead)
        lead_id = lead.id

    convo = Conversation(
        tenant_id=TENANT_ID,
        lead_id=lead_id,
        direction="inbound" if inbound else "outbound",
        message=message,
        channel="whatsapp"
    )
    db.add(convo)
    db.commit()
    return lead_id
```

Wire this into your WhatsApp callbacks:

```python
wa.on_inbound_message = lambda phone, name, msg: \
    log_whatsapp_to_lead(get_db_session(), phone, msg, inbound=True)
wa.on_outbound_message = lambda phone, msg: \
    log_whatsapp_to_lead(get_db_session(), phone, msg, inbound=False)
```

**Integration with lead detail page:** The existing `GET /api/leads/{id}` endpoint already queries the `Conversation` table — no separate endpoint needed. Any WhatsApp messages logged via the callback appear automatically on the lead's timeline/detail view.

## Dictation / Speech-to-Text Button

For chat interfaces where the user may want to dictate instead of type, add a microphone button next to the Send button using the browser-native **Web Speech API**. No API keys, no backend, works in Chrome.

**HTML:** Place the mic button between the textarea and the Send button:
```html
<button onclick="toggleDictation()" id="micBtn" class="mic-btn" title="Dictate">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
    <line x1="12" y1="19" x2="12" y2="23"/>
    <line x1="8" y1="23" x2="16" y2="23"/>
  </svg>
</button>
```

**CSS:**
```css
.mic-btn {
    background: transparent; border: 1px solid #d1d5db; border-radius: 12px;
    width: 42px; height: 42px; display: flex; align-items: center; justify-content: center;
    cursor: pointer; flex-shrink: 0; transition: all 0.2s;
    position: relative; color: #6b7280;
}
.mic-btn:hover { border-color: #60a5fa; color: #2563eb; }
.mic-btn.recording {
    border-color: #ef4444; color: #ef4444; background: #fef2f2;
    animation: mic-pulse 1.2s ease-in-out infinite;
}
@keyframes mic-pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.4); }
    50% { box-shadow: 0 0 0 8px rgba(239,68,68,0); }
}
```

**JavaScript:**
```javascript
var recognition = null;
var isRecording = false;
var dictationText = '';

function toggleDictation() {
    if (isRecording) { stopDictation(); return; }
    startDictation();
}

function startDictation() {
    var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        addMsg('Speech recognition not supported. Try Chrome.', 'agent');
        return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function(stream) {
        stream.getTracks().forEach(function(t) { t.stop(); });

        recognition = new SpeechRecognition();
        recognition.lang = 'en-US';
        recognition.continuous = true;
        recognition.interimResults = true;

        if (!dictationText && inp.value.trim()) {
            dictationText = inp.value.trim() + ' ';
        }

        recognition.onresult = function(e) {
            var interim = '';
            for (var i = e.resultIndex; i < e.results.length; i++) {
                var r = e.results[i];
                if (r.isFinal) {
                    dictationText += r[0].transcript + ' ';
                } else {
                    interim = r[0].transcript;
                }
            }
            inp.value = dictationText + interim;
            inp.style.height = 'auto';
            inp.style.height = Math.min(inp.scrollHeight, 180) + 'px';
        };

        recognition.onerror = function(e) {
            stopDictation();
            if (e.error === 'not-allowed') addMsg('Microphone access blocked.', 'agent');
        };
        recognition.onend = function() {
            if (isRecording && recognition) try { recognition.start(); } catch(e) {}
        };

        recognition.start();
        isRecording = true;
        document.getElementById('micBtn').classList.add('recording');
    }).catch(function() {
        addMsg('Microphone access denied.', 'agent');
    });
}

function stopDictation() {
    if (recognition) { recognition.stop(); recognition = null; }
    isRecording = false;
    document.getElementById('micBtn').classList.remove('recording');
}
```

### Hardcoded Values: Search Exhaustively Before Declaring Done

When changing a hardcoded string (lead name, icon, label, URL) that appears in the user-facing UI:

1. **`grep -rn 'old_value' project_dir/` BEFORE making any changes** — know the full surface area
2. **Change ALL occurrences**, not just the first one you find
3. **`grep` AFTER to confirm zero remaining**: `grep -c 'old_value' *` should return exit code 1 (no matches)
4. **Check across ALL template files** — the same value might exist in `dashboard_template.py`, `cadence_template.py`, `threads_template.py`, etc.
5. **Check both the HTML template** (initial render) **and JS code paths** (dynamic updates) — the ARA project often has both a static HTML initial value AND multiple JS functions that update the same element dynamically

**Why this bites in ARA specifically:** The codebase has 6+ separate files (server.py + multiple _template.py files) with overlapping UI patterns. A string that appears in one file is likely hardcoded in others too.

**Signal phrases to watch for:** User reports something "still showing old value" or "still says Rajesh" after you made a change.

### ARA Sidebar: Defined Per-Page, Not Shared

**Critical ARA codebase fact:** Each page in the ARA app defines its OWN sidebar HTML — there is no shared sidebar component or template include.

| Page | File | Sidebar location |
|------|------|-----------------|
| Dashboard | `dashboard_template.py` | ~line 822-844 |
| Cadence Builder | `cadence_template.py` | ~line 222-244 |

This means:
- Adding a new nav item to the dashboard sidebar does NOT add it to the cadence page
- Changing an icon/label/classification on one page must be manually replicated on the other
- The sidebar classifications (MAIN, INTELLIGENCE, LEARNING, CONFIGURATION) only exist in the dashboard — the cadence page sidebar was a flat list from an earlier build

**When to sync:** Whenever you add a nav item, change a nav label/icon, restructure sections, or reorder items — update BOTH files. The dashboard sidebar is canonical; replicate any changes to `cadence_template.py`'s sidebar.

### ARA Preview Lead: Every Code Path Must Be Updated

The cadence page preview lead label ("→ Rajesh Sharma, Acme Mfg" → "→ Gregory Ipe, Swiggy") is set in **6 separate places** in `cadence_template.py`:

1. **HTML template** (initial render on page load): `<span class="ph-lead" id="previewLead">`
2. **`renderSteps()`** — sets it when a step is selected
3. **`selectStep()`** — sets it when switching steps
4. **`switchTemplate()`** — sets it when switching templates
5. **Picker overlay + channel selection** — sets it when adding a new step
6. **Drag-and-drop reorder** — sets it when a step is moved

All 6 must be updated. Missing any one means clicking the wrong button still shows the old value.

**Prevention:** Before editing any hardcoded value that appears in the UI, run `grep -n 'old_value_here' project_file` to find every occurrence. Use a screen capture or list the line numbers before editing, then track progress against them.

## Induction-Driven Prefill Architecture (Path B)

For prototypes where an AI agent needs **structured configuration prompts** populated from live induction data (skills, conversation learnings, CRM data), use deterministic templates that read from the skills table at open-time. **No LLM call on open.**

### When to use Path B vs Path A

| Approach | Latency | Reliability | Content Quality | Determinism |
|----------|---------|-------------|-----------------|-------------|
| **Path B (templates)** | Instant | 100% | Good | Same data = same output |
| **Path A (LLM on open)** | 3-30s | Fragile (JSON/truncation) | Excellent | Varies per call |

**Recommendation:** Path B for production prefill. Path A for an optional "AI Generate" button on demand.

### Architecture Pattern

```
skills_table ──→ prefill_generator.py ──→ prefill endpoint (instant)
     ↑              (reads all skill keys, fills templates)
     │
     ├── Induction docs (human: gtm_learnings, guardrails, proposition)
     └── Conversation extraction (automated: objection_pattern, messaging_win)
```

The prefill endpoint:
1. Loads all skills from DB into a flat dict
2. Matches scaffold per cadence type (cold/inbound/nurture) — each has different persona, tone, vocabulary
3. Fills each section template using skill values as variables
4. Returns structured JSON — instant, deterministic, always valid

### Key Patterns

**Scaffolds per cadence type:**
```python
SCAFFOLDS = {
    "cold": {"persona_desc": "sophisticated, consultative, witty", "tone_chip": "sophisticated"},
    "inbound": {"persona_desc": "aggressive, qualifying, direct", "tone_chip": "confident"},
    "nurture": {"persona_desc": "informative, patient, educational", "tone_chip": "warm"},
}
```

**Fallback chain:** Every variable has a fallback so missing skills don't break output.

**Conversation enrichment:** Skill keys from extraction (`objection_pricing`, `follow_up_inbound_sequence`) are conditionally injected.

**GTM-operator voice:** Every section reads narrative and opinionated, not bullet-point generic.

**Testing the prefill:**
```bash
curl -s "http://localhost:8766/api/cadence/prefill?template_id=cold" | head -c 800
```

### Pitfalls
- Don't mix Path A + Path B in same endpoint — LLM failure silently degrades to templates
- Skills table must be populated before prefill looks correct
- Scaffold personas must feel distinctly different per cadence type
- Templates need maintenance when new skill categories are added
- Sections share the same skill data, so they're internally consistent by design

## Pitfalls

- **Always test your changes before releasing to the user** — Greg's explicit expectation: "Let's please test before release." After any change (UI, API, config), run a quick curl cycle or browser check and verify the actual output, not just that the server started.
- **curl success != browser success** — A curl test only verifies the server responds. It does NOT verify the frontend renders correctly, JavaScript loads without errors, API paths match between frontend and backend, or `typeof functionName === 'function'`. Always open the page with `browser_navigate`, click through the primary flow, and check `browser_console` for errors.
- **CSS grid columns stretch unevenly when content overflows `1fr` tracks** — When using `grid-template-columns: repeat(N, 1fr)` or `1fr 1fr ...`, grid items with overflowing content (long text, flex children with `min-width`) can distort the fr distribution, making columns visibly different widths even though the CSS says equal.

```css
/* BEFORE — columns go 155px, 203px, 243px, 94px instead of equal */
.lead-card-inner { display: grid; grid-template-columns: repeat(4, 1fr); }
.lead-card-section { padding: 20px; }

/* AFTER — min-width: 0 prevents content from distorting fr tracks */
.lead-card-section { padding: 20px 16px 24px; min-width: 0; word-break: break-word; }
```

**Three things to always set on grid items inside `1fr` tracks:**
- `min-width: 0` — prevents content from forcing the track wider (the main fix)
- `word-break: break-word` — wraps long strings so they don't overflow
- `overflow-wrap: break-word` — belts-and-suspenders for URL/text overflow

**Chat bubbles overflow horizontally without word-break** — message text (URLs, code, long words) spills off the right edge unless `.bubble` has `overflow-wrap: break-word; word-break: break-word; white-space: normal;`. This is the #1 visual bug in chat UIs. Always set these three on any message bubble class, regardless of max-width.
- **JS function names must match HTML onclick handlers** — if you rename a JS function (sendMessage -> sendMsg), update ALL onclick attributes on buttons too. Mismatched onclick references silently fail with empty console errors. Search for ALL references when renaming.
- **API URL path prefix consistency between frontend and backend** — This is the #1 silent bug in fast prototypes. When you add a new backend endpoint (`/api/induction/.../state`) but the frontend calls a different path (`/induction/chat/.../state`), the browser silently gets a 404 and the feature appears broken.

  **Prevention:**
  - Decide on ONE URL prefix convention at the start (e.g., all API endpoints under `/api/` or all under their logical path). Stick to it.
  - When adding a new endpoint, verify the frontend fetch URL matches the backend decorator EXACTLY.
  - **Always test with curl FIRST** before assuming the frontend will work.
  - **Always verify `typeof functionName === 'function'`** in the browser console after page load when debugging frontend JS that doesn't appear to work — if the function exists, the issue is probably a URL path or CORS issue.

- **FastAPI wraps bare string returns in JSON** — When a FastAPI endpoint does `return "raw_text"`, FastAPI serializes it as `JSONResponse` with content `"raw_text"` (with JSON quotes around the string). For base64 images returned to the frontend for data URLs (`<img src="data:image/png;base64,...">`), HTML snippets, or any non-JSON response body, this breaks the consumer — embedded quotes make the data URL invalid.

  **Fix:** Use `from fastapi import Response` and return `Response(content=data, media_type="text/plain")` (or the appropriate media type):

  ```python
  from fastapi import Response

  @app.get("/api/whatsapp/qr")
  def whatsapp_qr():
      qr = get_qr_base64()  # returns raw base64 string
      if qr:
          return Response(content=qr, media_type="text/plain")
      return Response(content="WAITING", media_type="text/plain")
  ```

  Verify by checking the first 3 response bytes with curl — `iVB` (PNG header) means clean pass-through. `"iV` means JSON-wrapped — fix it.

- **Python triple-quoted string escaping in embedded HTML/JS** — Inside a Python string (`'...'`, `"..."`, or `"""..."""`), `\'` is a recognized escape that produces a bare `'` (Python consumes the backslash). This is the #1 cause of silently broken inline JavaScript.

  **The bug pattern (`\'` in Python → `'` in JS):**
  ```python
  # Inside """...""": Python sees \' as an escape → outputs just '
  '...<h3>Ava\'s Learnings...</h3>...'
  ```
  Renders in browser as: `<h3>Ava's Learnings...` — the `'` after `Ava` terminates the JS string literal, and the entire 130KB+ script block silently fails to parse.

  **Why other `\'` patterns seemed OK:** When `\'` lands inside an HTML `onclick=""` attribute (not inside a JS string's content), the resulting `'` creates `''` (empty strings in JS), which is valid:
  ```python
  # Inside """...""": \' + a.id + \' → '' + a.id + ''
  cancelBtn = '<span onclick="cancelAction(\'' + a.id + '\')">Cancel</span>'
  ```
  Renders as `onclick="cancelAction('' + a.id + '')"` — `''` is an empty string, so `cancelAction('someId')` works. But this is accidental, not intentional — the same pattern with possessive text (`Ava's`) breaks.

  **The real takeaway:** NEVER use `\'` to mean "a single quote in the JS output" inside a Python string. It produces the character, but you lose the backslash — and when that character ends up in JS string content (not an HTML attribute), it breaks everything.

  **Fix #1 — Event delegation (PREFERRED):** Never use inline onclick/onchange with string arguments. Use `data-*` attributes and a single delegated listener:

  ```python
  # What you write:
  '<tr onclick="showLeadDetail(\\\'' + l.id + '\\\')">'
  # What Python outputs:
  '<tr onclick="showLeadDetail(\'\' + l.id + \'\')">'
  # What the browser parses:
  onclick="showLeadDetail(''"  (attribute closes here)
  # JS error: SyntaxError: Unexpected string
  ```

  **Fix #1 — Event delegation (PREFERRED):** Never use inline onclick/onchange with string arguments. Use `data-*` attributes and a single delegated listener:

  ```python
  # Python: data-id has no quotes to escape
  '<tr data-id="' + l.id + '" class="lead-row">'
  ```

  ```javascript
  // JS: single delegated listener at bottom of script
  document.getElementById('centerPanel').addEventListener('click', function(e) {
      var row = e.target.closest('.lead-row');
      if (row) showLeadDetail(row.dataset.id);
  });
  ```

  **For `<select>` change events** (which fire differently from click):
  ```javascript
  document.addEventListener('change', function(e) {
      var t = e.target.closest && e.target.closest('[data-action="change-cadence"]');
      if (!t) return;
      updateLeadCadence(t.dataset.leadId, e.target.value);
  });
  ```
  The `change` event on `<select>` bubbles naturally, so a single document-level listener works just like click delegation.

  **Fix #2 — Reword (fallback):** Avoid apostrophes in JS strings embedded in Python:
  - `You've` -> `You have`
  - `Let's` -> `Let us`
  - `I'll` -> `I will`

  **Fix #3 — `\\x27` (JS hex escape) for inline onclick in Python strings:**

  When you can't convert to event delegation (hundreds of existing inline handlers across a large template), use JavaScript's `\x27` hex escape for single quotes. The key: you need a **double backslash** in the Python source so Python emits `\x27` for JS to decode:

  ```python
  # WRONG — single backslash: Python interprets \x27 as a hex escape → outputs bare '
  '...onclick="cancelAction(\x27' + a.id + '\x27)"...'
  # Python outputs: ...onclick="cancelAction('' + a.id + '')"...
  #                     ^^ empty strings — JS breaks

  # CORRECT — double backslash: Python outputs \x27, JS decodes it as '
  '...onclick="cancelAction(\\x27' + a.id + '\\x27)"...'
  # Python outputs: ...onclick="cancelAction(\x27abc123\x27)"...
  # JS interprets:  \x27 → '  →  onclick="cancelAction('abc123')"  ✓
  ```

  **Rule of thumb — how to get a single quote `'` in JS output from Python strings:**

  | Python source | Python produces | JS sees | What it means in JS |
  |---|---|---|---|
  | `\x27` | `'` (Python hex escape consumed) | `'` | **BREAKS** — terminates JS string |
  | `\'` | `'` (Python escape consumed) | `'` | **BREAKS** — terminates JS string |
  | `\\'` | `\'` (backslash preserved as literal) | `\'` → `'` | Works — JS escape |
  | `\\x27` | `\x27` (backslash preserved as literal) | `\x27` → `'` | Works — JS hex escape |
  | `\\\\x27` | `\\x27` (two backslashes) | `\\x27` → `\x27` (literal text) | Wrong — not decoded |

  **Key insight:** In ALL Python string types, one backslash before a special character (`'`, `"`, `x`, `n`) creates a Python escape. Two backslashes make the backslash literal, preserving it for JS to process.

  **Fix #4 — `\n` (backslash-n) in JS inside Python strings:** Python interprets `\n` as a literal newline character (0x0A), NOT as the two-character sequence backslash-n. This silently breaks JS strings that contain `\n` escape sequences:

  ```python
  # What you write (inside """..."""):
  var msg = 'Line one:\nLine two'  # Python sees \n → actual newline

  # What Python outputs:
  var msg = 'Line one:
  Line two'  # JS syntax error — string spans two lines

  # What you need:
  var msg = 'Line one:\\nLine two'  # Python sees \\n → \n (backslash + n)

  # What Python outputs:
  var msg = 'Line one:\nLine two'  # Valid JS — \n is newline escape
  ```

  **Rule of thumb:** Inside a Python triple-quoted string (`"""..."""`), every `\` that needs to appear in the output must be written as `\\`. For JS escape sequences like `\n`, `\t`, `\"`, `\'`, always double the backslash.

  **Verification workflow after any edit to embedded JS:**
  1. Extract the inline script and check syntax:
     ```bash
     python3 -c "import re; open('/tmp/js.js','w').write(re.search(r'<script>(.*?)</script>', open('/tmp/page.html').read(), re.DOTALL).group(1))"
     node -c /tmp/js.js
     ```
  2. Must exit 0 with no errors. If it fails, find the error line and inspect the raw bytes:
     ```bash
     sed -n '<LINE>p' /tmp/js.js | xxd
     ```
     Look for `27` (bare single-quote byte 0x27) where you expected `5c 78 32 37` (`\x27`) or `0a` (actual newline) where you expected `5c 6e` (backslash-n).

  3. **Verify Python's actual output bytes** — don't trust what you think the template produces:
     ```bash
     curl http://localhost:8766/dashboard | grep "Ava" | xxd | head -10
     ```
     If you see `27` (single quote byte 0x27) where you expected `5c 78 32 37` (`\x27`), Python is eating your escape sequence.

  4. Open in browser, verify `typeof yourFunction === 'function'` in console.
  5. Check `browser_console` for fetch URL mismatches (method GET vs POST is the #1 cause) and null/undefined responses.

**HTML entity escaping for dynamic content in innerHTML** — When building HTML strings that include user-controlled data (lead names, tooltip text, API responses), always escape to prevent broken rendering and XSS:

```javascript
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
```

Usage: `'<span class="tooltip">' + esc(tipText) + '</span>'`

Without `esc()`, text containing `<` or `&` breaks the HTML. This is especially important for tooltip text, dropdown labels, and any content rendered via `innerHTML` assignment.

Debugging catch-block errors — When a function silently fails and renders an error message (Error loading lead), check whether a variable/function used in the try block is undefined. The #1 cause in this codebase: calling esc() without it being defined. Search the file for the function name to confirm it exists before diving deeper into the logic.

DOM-sync functions must not re-initialize the source array before reading the DOM — In a saveCurrentState() / DOM-sync pattern where you read from DOM inputs and write to a state object, NEVER set the source array to [] before iterating the DOM. If the DOM represents a subset of the state (e.g., only displays descriptions but not channel/timing data), clearing the array permanently loses the non-DOM fields.

```javascript
// WRONG — clears all steps, loses channel/day/delay/fields
t.steps = [];
stepCards.forEach(function(card, i) {
    t.steps[i].desc = card.querySelector('.step-objective').value;
});

// RIGHT — update descriptions in-place, never touch the array reference
stepCards.forEach(function(card, i) {
    if (i < (t.steps || []).length) {
        t.steps[i].desc = card.querySelector('.step-objective').value;
    }
});
```

Check for this pattern anytime a function reads DOM data and the output is missing fields that are not in the DOM.

## Structured LLM Fields Pattern

For LLM-powered form previews where the user needs precise control over output structure (cadence step previews, email drafts, call scripts), see references/structured-llm-fields-pattern.md. The core idea: split one vague objective box into named slots (Opening, Value, CTA) that map 1:1 to output sections. The LLM fills language around the user's structure — no iteration needed.
