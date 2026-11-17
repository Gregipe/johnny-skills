# WhatsApp Headless Browser Setup (Playwright)

## How WhatsApp Auth Works

ARA uses Playwright to launch a persistent Chromium browser that loads web.whatsapp.com. The user scans a QR code once, and the session persists in `~/.hermes/ara_whatsapp_profile` (Playwright's `user_data_dir`). On subsequent restarts, the loaded profile should restore the session.

## Startup Timing

WhatsApp startup takes **~53 seconds total**:
- Playwright browser launch + navigation to web.whatsapp.com: ~20s
- Page wait for canvas/chat-list selector: 25s timeout
- Post-render sleep: 2s
- QR capture / auth check: ~5s

**Do NOT check `_ready` or `is_connected` before 55 seconds.** The `_start_wa()` thread launched by the connect endpoint is a daemon thread — it won't block server startup. The status endpoint may return stale data during this window.

## Critical Launch Flags

**Do NOT use `--disable-gpu`** — this flag prevents canvas rendering in headless Chromium. WhatsApp Web renders its QR code as a `<canvas>` element. Without canvas rendering, the QR code never appears. The page loads but `_capture_qr()` returns `None`.

**Do NOT add `--headless=new` as a Chromium flag** when also passing `headless=True` to `launch_persistent_context()`. The `headless=True` parameter and `--headless=new` flag conflict, causing the Playwright Node.js driver to crash with an `EPIPE` error. Either use `headless=True` (the parameter) without the flag, or `headless=False` with `--headless=new`. The current code uses `headless=True` (the parameter) which works correctly once `--disable-gpu` is removed.

```python
launch_args = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-popup-blocking",
    "--disable-notifications",
    # NO --disable-gpu (kills canvas for QR code)
    # NO --headless=new (conflicts with headless=True param → EPIPE crash)
]
```

If you need to test QR rendering manually with the same args:

```python
async def test():
    from playwright.async_api import async_playwright
    p = await async_playwright().start()
    ctx = await p.chromium.launch_persistent_context(
        user_data_dir='/tmp/test_wa',
        headless=True,
        args=['--no-sandbox', '--disable-blink-features=AutomationControlled'],
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.goto('https://web.whatsapp.com', wait_until='load', timeout=30000)
    await asyncio.sleep(5)
    canvases = await page.query_selector_all('canvas')
    print(f'QR canvas present: {len(canvases) > 0}')
    # If true, QR is rendering. Scan the canvas or check /api/whatsapp/qr
```

## Session Persistence

The profile at `~/.hermes/ara_whatsapp_profile` survives server restarts. However:

- **After ~5+ rapid restarts**, WhatsApp's server invalidates the session (too many browser reconnects). The page loads but QR code is shown instead of the chat list.
- **The persistent profile can become corrupted** — Playwright writes browser state (localStorage, IndexedDB, cookies) to this directory. If Playwright is killed abruptly (SIGKILL), the profile may become inconsistent.
- **Fix**: delete the profile (`rm -rf ~/.hermes/ara_whatsapp_profile`), restart the server, and scan the QR code fresh.

## Diagnosis

| Symptom | Status API | Likely Cause |
|---------|-----------|--------------|
| "Starting WhatsApp Web..." stuck | `connected: true, authenticated: false` | QR canvas not rendering (check --disable-gpu was removed) |
| "Waiting for QR scan" but no image | QR API returns "WAITING" | Canvas exists but `_capture_qr()` hasn't polled yet, or profile is corrupt |
| "Could not restore session" | `authenticated: false, session_exists: true` | Session invalidated by WhatsApp (too many restarts) |
| Playwright EPIPE crash | Server process may still be up | Node.js driver crashed — check `--headless=new` + `headless=True` conflict first |
| Status says "Authenticated" but no messages send | `connected: true, authenticated: true` | **Stale cached auth.** The `_status()` method has a 120-second cache window. If Playwright crashed, the cache returns old data. Check `wa._ready` and `wa.page` directly. |

### Stale Status Cache Bug

The WhatsApp status endpoint caches auth results for 120 seconds:

```python
if not live_authed and self._cached_auth and (time.time() - self._last_auth_check) < 120:
    authed = True  # Uses stale cache!
```

This means even after Playwright crashes with EPIPE, the status API reports "Authenticated" for up to 2 minutes. The Integrations page shows a green check even though no messages can be sent.

**Workaround**: If the Integrations page shows WhatsApp as connected but messages aren't going through, check `wa._ready` directly (it will be `False`). Or wait 120 seconds for the cache to expire.

## EPIPE Crash

The `write EPIPE` error means the Node.js Playwright driver process crashed. Common causes:
- **`--headless=new` + `headless=True` conflict** — Don't mix the flag with the parameter. Use one or the other.
- **Playwright browser not installed**: Run `python3 -m playwright install chromium`
- **Out-of-date Playwright**: `pip install --upgrade playwright && python3 -m playwright install chromium`

## QR Page Polling Race

The QR display page at `/api/whatsapp/link` has a 2-second polling loop that fetches `/api/whatsapp/status` and `/api/whatsapp/qr`. If the page is opened BEFORE WhatsApp finishes starting (~53s), the initial poll sees `WAITING` and the page shows "Starting WhatsApp Web..." permanently — the JavaScript polling code may stop working after the first few cycles if the browser console/page state gets confused.

**Fix**: Always hard-refresh (Cmd+Shift+R) the QR page after WhatsApp has finished starting (`/api/whatsapp/status` returns `connected: true, message: "Waiting for QR scan"`). Do NOT load the page early and wait for it to update automatically.

## Re-auth Flow

1. Open `http://localhost:8766/api/whatsapp/link` in a browser
2. Wait ~55s for WhatsApp to start (check status with `curl http://localhost:8766/api/whatsapp/status`)
3. Hard-refresh the page once status shows "Waiting for QR scan"
4. The page polls `/api/whatsapp/status` every 2s and shows the QR code when ready
5. Open WhatsApp on phone → Menu → Linked Devices → Link a Device
6. Scan the QR code
7. The page auto-detects authentication and shows "Connected!"

## Avoid Rapid Restarts

Each `pkill -f` kills the Playwright browser process. Restarting the server rapidly (>5 times) will cause WhatsApp to invalidate the session. When debugging code changes:

- Try to make changes without restarting (hot-reload, or batch changes)
- If a restart is necessary, the profile may survive 1-2 restarts
- After 3+ restarts, expect to re-scan the QR code
