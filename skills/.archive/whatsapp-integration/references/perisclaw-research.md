# Perisclaw & OpenClaw Self-Chat Research

## Context
Discovered while debugging why Baileys `messages.upsert` doesn't fire for self-chat replies in ARA's coaching flow. Greg had used Perisclaw before and expected the same "reply to self-chat" UX.

## Key Findings

### Perisclaw (perisclaw.com)
- Runs on user's **personal WhatsApp number** (same as ARA)
- Uses WhatsApp multi-device protocol (same as Baileys)
- Does NOT need a business API — standard WhatsApp personal number
- Reads conversation history from Day 1 on first connect
- Self-chat replies work seamlessly without any extra user steps

### OpenClaw (GitHub)
- Open-source WhatsApp bot similar to Perisclaw
- Uses `@whiskeysockets/baileys` (same library as ARA)
- Has explicit `selfChatMode: true` configuration option
- Tracks outbound message IDs to filter echoes (same pattern as our `sentMsgIds` Set)
- Known Baileys issue #415: LID (Local ID) resolution fails for self-chat — WhatsApp sometimes uses `@lid` JIDs instead of `@s.whatsapp.net`

### How They Detect Self-Chat Replies

| Method | Evidence | Status |
|--------|----------|--------|
| **`chats.update` event** | Baileys docs: fires "on every message" including self-chat | ✅ **CONFIRMED** — implemented in ARA sidecar. Uses `chatTimestamps` tracking Map to detect new messages via timestamp/unreadCount comparison. The `lastMessage` field carries the full message content. |
| `emitOwnEvents: true` + `messages.upsert` | Both use same Baileys lib | ❌ Does NOT work — self-chat messages never fire `messages.upsert` regardless of setting |
| `messages.set` event | Fires during history sync, may include self-chat | ❌ Not needed — `chats.update` works in real-time, no sync dependency |
| `messaging-history.set` event | Full history event on reconnect | ❌ Not needed — real-time via `chats.update` |
| Baileys fork/patch | OpenClaw changes Baileys behavior | ❌ Not needed — upstream Baileys fires `chats.update` for self-chat |
| Polling chat list | Periodically check recent conversations | ❌ Not needed — event-driven via `chats.update` |
| Group-based routing | Create hidden group internally | **Fallback** — only needed if `chats.update` fails for a specific Baileys version |

## Real-World Verdict (June 2026)

After extensive testing, here's what actually works:

| Method | Status | Notes |
|--------|--------|-------|
| **WhatsApp Group** ✅ | **RELIABLE** — always fires `messages.upsert(notify)` | Create a group, use for coaching. Group messages go through WhatsApp servers. |
| `chats.update` event ❌ | **UNRELIABLE** — `lastMessage` often absent from payload | Implemented but real-world testing confirmed it doesn't consistently fire with message content. The `Partial<Chat>` update object frequently omits `lastMessage`. |
| `emitOwnEvents: true` ❌ | Does NOT work for self-chat | Self-chat messages never fire `messages.upsert` regardless of setting. Needed for lead-reply detection but no help for self-chat. |

**Conclusion**: Perisclaw likely does NOT use Baileys for self-chat - they probably use a WhatsApp Web UI poller (Playwright scraping IndexedDB) or a custom WhatsApp client that reads local storage. The `chats.update` approach works in theory but fails in practice because Baileys' `Partial<Chat>` update doesn't include `lastMessage` reliably.

ARA's fix: WhatsApp group approach documented in `references/group-coaching.md`.

## ARA Current State (as of June 2026)

### What Actually Works

1. **`emitOwnEvents: true`** in sidecar — required for owner reply detection (non-self-chat)
2. **`sentMsgIds` echo filter** — Set tracks outbound IDs, 30s TTL cleanup  
3. **WhatsApp Group coaching** — Group JID `120363429248150974@g.us`, server uses `send_to_jid()` 
4. **Owner group reply detection** — `fromMe + !sentMsgIds + @g.us` in `messages.upsert`, phone from `sock.user.id`
5. **Server routing fix** — `is_owner` checked BEFORE `_find_lead_by_phone` for `owner_reply` messages
6. **`tenant_id=TENANT_ID`** on all `AgentChatMessage` creates
7. **`"Ava: "` prefix** on all outbound to owner

### What Was Tried and Failed

- `messages.upsert` with `emitOwnEvents: true` — doesn't fire for self-chat
- `chats.update` with `lastMessage` extraction — fires but `lastMessage` often absent
- `messages.set` / `messaging-history.set` — only fires on reconnect, not real-time

### OpenClaw Echo Issues

OpenClaw's open issues reveal the same challenges:
- Echo loops from `emitOwnEvents: true` (outbound messages ingested as inbound) — fixed by echo filter
- Self-chat messages arriving as `append` type (not `notify`) — OpenClaw was skipping `append` type, losing messages
- Some chose to add anti-self-reply instructions in the system prompt as an additional safeguard

### Still Untested
- LID format detection — whether `@lid` JIDs from WhatsApp's newer addressing scheme break `chats.update` as well (they shouldn't, since `chats.update` uses the same JID format)
- Group-based routing — hasn't been needed since `chats.update` works
