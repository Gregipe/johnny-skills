# WhatsApp Session Persistence — Persistent Context vs storage_state

**Discovery date:** May 2026
**Applies to:** Any ARA WhatsApp integration, or any Playwright-based web automation where auth tokens need to survive restarts

## The Problem

WhatsApp Web session tokens were lost on every server restart. Despite using `context.storage_state()` to save and restore the session, re-authentication was required after every restart.

**Observable symptoms:**
1. Starting server → QR code shows → scan with phone → "Connected" badge
2. Send a message via `/api/whatsapp/send` → connection drops → QR shows again
3. Restart server → QR code shows again (re-auth needed)

## Why It Happened

Playwright's `storage_state()` only captures two things:
- **Cookies** — WhatsApp Web uses these for some session data
- **localStorage** — used for some preferences

**It does NOT capture IndexedDB** — and that's where WhatsApp Web stores its critical authentication tokens.

```
storage_state() → cookies + localStorage only  ❌
                 → IndexedDB MISSING
                 → restore gives WhatsApp a partial session
                 → WhatsApp forces full re-auth → QR code
```

When we inspected the saved session JSON, it had only 3 cookies and 1 origin — far less than what a real WhatsApp Web session needs.

## The Fix: launch_persistent_context()

Replace `launch() + new_context() + storage_state()` with a single `launch_persistent_context()` call that uses a Chromium user data directory:

### Before (broken):

```python
async def _start(self):
    self.playwright = await async_playwright().start()
    self.browser = await self.playwright.chromium.launch(headless=True)
    if os.path.exists(SESSION_FILE):
        self.context = await self.browser.new_context(storage_state=SESSION_FILE)
    else:
        self.context = await self.browser.new_context()
    self.page = await self.context.new_page()

async def _send_message(self, number, text):
    # Navigates the MAIN page to send — disrupts WhatsApp Web session
    await self.page.goto(url)
```

### After (fixed):

```python
USER_DATA_DIR = os.path.expanduser("~/.hermes/ara_whatsapp_profile")

async def _start(self):
    self.playwright = await async_playwright().start()
    # Persistent context preserves ALL state — cookies, localStorage, IndexedDB
    self.context = await self.playwright.chromium.launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    self.page = self.context.pages[0]

async def _send_message(self, number, text):
    # Use a TEMP page that shares the same context
    # Main page stays on WhatsApp Web for keepalive
    temp_page = await self.context.new_page()
    try:
        await temp_page.goto(url, wait_until="domcontentloaded", timeout=15000)
        # ... click send button ...
    finally:
        await temp_page.close()
```

### Key Differences

| Aspect | storage_state() | launch_persistent_context() |
|--------|-----------------|----------------------------|
| Saves cookies | ✅ Yes | ✅ Yes (auto) |
| Saves localStorage | ✅ Yes | ✅ Yes (auto) |
| Saves IndexedDB | ❌ **No** | ✅ Yes (auto) |
| Saves service workers | ❌ No | ✅ Yes (auto) |
| Saves WebSQL / Cache API | ❌ No | ✅ Yes (auto) |
| Restore method | `new_context(storage_state=file)` | `launch_persistent_context(user_data_dir=dir)` |
| File format | Single JSON file | Full Chromium profile directory |
| First use | Set up manually | Auto-created on first launch |

## The Second Bug: Send Navigates Main Page

Even with persistent context, sending a message via `page.goto(url)` navigates the **main page** away from `web.whatsapp.com`, which breaks the WhatsApp Web session. On restoration, WhatsApp might detect the interruption and require re-auth.

**Fix:** Use a **temporary page** for sending operations. The temp page shares the same persistent context (same IndexedDB, cookies, etc.) and closes after sending:

```python
async def _send_message(self, number, text):
    temp_page = await self.context.new_page()
    try:
        await temp_page.goto(url, wait_until="domcontentloaded", timeout=20000)
        # Find and click send button
        send_btn = await temp_page.wait_for_selector(
            'button[data-testid="compose-btn-send"], button[aria-label="Send"]',
            timeout=10000
        )
        if send_btn:
            await send_btn.click()
            return {"success": True}
        return {"error": "Send button not found"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        await temp_page.close()
```

## The Third Bug: Auth Detection Must Be Real

A common pitfall is checking `div#app` exists on the page as a proxy for "authenticated." But `div#app` exists from the moment WhatsApp Web loads — it doesn't mean the user scanned the QR.

**Correct auth check:**

```python
async def _check_auth(self):
    """Check if user is truly authenticated (QR scanned, chat list visible)."""
    try:
        # Use the real auth indicators — chat list visible after login
        chat_list = await self.page.query_selector('[data-testid="chat-list"]')
        if chat_list:
            return True
        # Or check for a conversation panel element
        conv_panel = await self.page.query_selector('[data-testid="conversation-panel"]')
        if conv_panel:
            return True
        return False
    except Exception:
        return False
```

## Verification Checklist

After applying the persistent context fix:

1. ✅ Start server → navigate to Integrations page → toggle WhatsApp
2. ✅ QR code displays → scan with phone
3. ✅ Badge shows "Connected" after scan
4. ✅ Send a test message via API — connection persists
5. ✅ **Restart server** — WhatsApp should NOT require re-scan
6. ✅ Verify with `_get_integration_status` returning `authenticated: true` after restart
7. ✅ Send another message — verify connection still holds
