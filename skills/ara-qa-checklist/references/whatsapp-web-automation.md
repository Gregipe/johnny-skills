# WhatsApp Web Automation — ARA Integration

## Architecture (v2 — Persistent Connection)

### Singleton Manager
```python
wa = WhatsAppManager()  # global singleton in whatsapp_manager.py
```

### Lifecycle States
| State | `_ready` | Browser | Auth Check | `_status()` message |
|-------|----------|---------|------------|---------------------|
| Not started | False | None | — | "Not started" |
| Starting | True | Launching | False | "Waiting for QR scan" |
| QR ready | True | Running + canvas | False | "Waiting for QR scan" |
| Authenticated | True | Running + chat list | True | "Authenticated" |

### Key Design Decisions

1. **`is_authenticated` must actually check auth** — Not just `is_connected` (browser running). Calls `_check_auth()` which looks for post-auth DOM elements (`div[data-testid="chat-list"]`, `div[data-testid="conversation-panel"]`) and returns `False` if a QR canvas is present.

2. **Auth check failure modes:**
   - `div#app` is the React mount point — **always exists**, even on QR page. Never use it for auth detection.
   - Canvas element = not authenticated (still on QR page)
   - `header` exists on both pages but has different content — check for `[data-testid="menu"]` inside it

3. **Backend status mapping pattern (`server.py`):**
   ```python
   def _get_integration_status(integration_id):
       if integration_id == "whatsapp-self":
           status = wa.status_sync()
           authed = status.get("authenticated", False)
           return {"connected": authed, "authenticated": authed}
   ```
   This is critical because `list_integrations` does `status.get("authenticated", False) OR status.get("connected", False)`. If `connected` is anything but tightly coupled to `authenticated`, the badge goes green before QR scan.

4. **Anti-detection:** WhatsApp Web headless is detected without these:
   ```python
   launch_args = ["--disable-blink-features=AutomationControlled", ...]
   await page.add_init_script("""
       Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
       Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
       Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
   """)
   ```
   Also set: realistic viewport (1280x800), locale (`en-US`), modern user agent.

5. **Keepalive:** Background asyncio task pings every 30s. Checks `page.url` contains `web.whatsapp.com`. Reloads if drifted. If auth lost (keepalive cycle finds `_check_auth()` returns False), reloads page. Cancelled in `_stop()`.

### Send Flow (v2)

```
toggle clicked → POST /api/integrations/whatsapp-self/connect
                → backend starts WhatsApp thread (if not running)
                → returns {"status": "starting", "redirect": "/api/whatsapp/link"}
                → frontend: set CONNECTING_IDS[id]=true, show inline QR, start poll

Poll (every 3s):
  GET /api/whatsapp/status → check authenticated
  GET /api/whatsapp/qr     → display QR image

User scans QR → poll detects authenticated:true
              → delete CONNECTING_IDS[id], clear poll, renderIntCards()
              → badge flips to "Connected"

User clicks toggle OFF → POST /api/integrations/whatsapp-self/disconnect
                       → wa._ready=False, page.close()
                       → delete CONNECTING_IDS[id], render → badge "Not connected"
```

### QR Endpoint Gotcha
FastAPI's default response wrapping causes `return qr` to JSON-wrap the base64 string as `"iVBOR..."` (with quotes). The browser then sees `data:image/png;base64,"iVBOR..."` which **breaks the image**.

**Fix:** Use `Response(content=qr, media_type="text/plain")` from `fastapi.responses` (or import `Response` directly).

### Common Failures

| Symptom | Root cause | Fix |
|---------|-----------|-----|
| `AttributeError: module 'urllib' has no attribute 'quote'` | `__import__("urllib.parse")` returns top-level `urllib`, not `urllib.parse` | `from urllib.parse import quote` |
| Badge shows "Connected" before QR scan | `_get_integration_status` returns `connected` from `is_connected` (browser running) instead of `authenticated` | Map `authenticated` → `connected` in status function |
| Toggle snaps back to off after click | `renderIntCards()` runs after connect and backend returns `connected: false` | Use `CONNECTING_IDS` global to keep toggle checked during window |
| QR shows as broken image | FastAPI JSON-wraps the base64 string | `Response(content=qr, media_type="text/plain")` |
| Send button not found | Page reload triggers overlays/updates blocking the button | Add `_dismiss_overlays()` before button search |
| Session lost after server restart | No session file or file not loaded | Check `~/.hermes/ara_whatsapp_session.json` exists; `context = browser.new_context(storage_state=...)` loads it |
| Headless browser detected | No anti-detection measures | Add `AutomationControlled` flag and `navigator.webdriver` override |

### Session Persistence
- Session saved: `~/.hermes/ara_whatsapp_session.json`
- QR cache: `~/.hermes/ara_qr.png`
- On server start, if session file exists, `_start()` loads it into `new_context(storage_state=...)` and attempts to restore the authenticated page
- Session saved in two places: (1) in `_wait_for_auth()` immediately after QR scan detected, (2) in `_send_message()` after successful send

### Debugging
- Server log: check `logger.info` / `logger.error` from `whatsapp_manager.py`
- QR endpoint: `curl -s http://localhost:8766/api/whatsapp/qr | head -c 5` — first chars should be `iVBOR` (PNG), not `"` (JSON)
- Status: `curl -s http://localhost:8766/api/whatsapp/status`
- Integration list: `curl -s http://localhost:8766/api/integrations | python3 -m json.tool`
- Debug screenshot saved to `/tmp/whatsapp_debug.png` when send button not found
- Playwright version: Chromium bundled with installed `playwright` package
