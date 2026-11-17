# Playwright Fallback (Merged from whatsapp-web-automation)

> **Source:** This content was merged from the now-deprecated `whatsapp-web-automation` skill. The authoritative reference for WhatsApp automation in ARA is the parent skill `whatsapp-integration`.

## When to Use Playwright

Only use Playwright as a fallback when Node.js runtime is unavailable. The primary approach is Baileys (see main skill).

| | **Baileys (✅ Preferred)** | **Playwright (Fallback)** |
|---|---|---|
| Approach | Node.js WebSocket — speaks MD protocol directly | Headless Chromium — controls web.whatsapp.com UI |
| Startup | ~2 seconds | ~30-60 seconds |
| Memory | ~50MB | ~500MB |
| Survives server restarts | ✅ Auth persisted to disk | ❌ Dies every restart |
| Send reliability | Protocol-level | DOM click — breaks when UI changes |
| Runtime dependency | Node.js | Python + Playwright + Chromium |

## Key Differences from Baileys

1. **Event Loop Architecture** — Playwright requires a dedicated event loop thread with `run_coroutine_threadsafe()`
2. **Session Persistence** — Use `launch_persistent_context()` with `user_data_dir` to preserve IndexedDB auth
3. **Inbound Detection** — Must poll DOM for unread badges (fragile) vs Baileys event-based
4. **Sending Messages** — Use a temp page per send (never navigate the main page)

## Critical Pitfalls

- `--disable-gpu` breaks canvas rendering — QR code never shows
- `--headless=new` conflicts with `headless=True` parameter
- `storage_state()` does NOT export IndexedDB — use persistent context
- User agent MUST include `Chrome/<version>` token
- QR canvas can take 30-60 seconds to render

## See Also

- `whatsapp-integration` skill — authoritative reference for ARA WhatsApp automation
- Main skill's "Playwright Approach (Fallback)" section for full implementation details
