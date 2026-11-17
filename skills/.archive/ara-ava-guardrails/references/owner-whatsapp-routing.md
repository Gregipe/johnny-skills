# Owner WhatsApp Routing — Coaching Thread & Prefixes

## Flow Overview

The owner can interact with Ava via WhatsApp the same as the dashboard chat. Two directions:

### Outgoing (Ava → Owner)

```
Ava response → _handle_owner_coach_whatsapp
  → wa.send_message_sync(admin.phone, "Ava: " + ava_reply)
```

Every message sent TO the owner's number MUST be prefixed with `"Ava: "` so the owner can distinguish system messages from their own replies.

**Places that send to owner:**

| Location | Has prefix? |
|---|---|
| `send_whatsapp_to_owner` tool handler (~line 3291) | ✅ `"Ava: " + message` |
| `_send_owner_alert` (~line 7587) | ✅ `"Ava: " + message` |
| Coaching reply in `_handle_owner_coach_whatsapp` (~line 7657) | ✅ `"Ava: " + ava_reply` |

All three must always prefix. If adding a new outbound owner path, add the prefix.

### Incoming (Owner → Ava)

When the owner replies to an "Ava: ..." message on WhatsApp, the Baileys sidecar (port 8767) detects it and POSTs to `POST /api/whatsapp/inbound`.

**Sidecar detection logic** (`whatsapp-sidecar/index.js` ~line 153):

```javascript
if (isFromMe) {
  // Owner sent a message — POST with owner_reply: true
} else {
  // Incoming from someone else — POST with owner_reply: false
}
```

**Server routing** (`whatsapp_inbound_webhook` ~line 7465):

```python
if owner_reply:
    lead = find_lead_by_phone(phone)
    if lead:
        log_owner_reply_to_lead(phone, message)  # Owner replying to a lead
    elif is_owner:
        handle_owner_coach_whatsapp(phone, message)  # Owner in coaching thread
else:
    if is_owner:
        handle_owner_coach_whatsapp(phone, message)  # Owner's own incoming
    else:
        lead = find_lead_by_phone(phone)
        if lead:
            handle_inbound_from_lead(phone, message)  # Lead message
```

The `is_owner` check matches the admin phone from the User table (flexible suffix matching).

### `_handle_owner_coach_whatsapp` (~line 7593)

This is the core function that routes owner WhatsApp messages to the dashboard chat:

1. Finds or creates a `ChatThread` with `thread_type="coaching"`
2. Sends 👍 reaction to acknowledge (best-effort)
3. Saves owner's message as `AgentChatMessage(role="user", ...)`
4. Calls `POST /api/agent/chat/{TENANT_ID}` — same endpoint as the dashboard UI
5. Saves Ava's response as `AgentChatMessage(role="assistant", ...)`
6. Sends response back to owner via WhatsApp with "Ava: " prefix

## ⚠️ Known Pitfalls

### 1. Missing `tenant_id` on AgentChatMessage (SILENT FAILURE)

```python
# ❌ WRONG — causes silent failure
msg = AgentChatMessage(thread_id=thread.id, role="user", content=message)

# ✅ CORRECT — includes tenant_id
msg = AgentChatMessage(
    thread_id=thread.id,
    tenant_id=TENANT_ID,    # ← Required! NOT NULL constraint
    role="user",
    content=message,
)
```

The `agent_chat_messages.tenant_id` column has a NOT NULL constraint. Omitting it causes an `IntegrityError` that gets caught by the generic exception handler and logged to an internal ring buffer. The webhook returns `{"status": "ok"}` but the message is never saved and no response comes back to the owner — **complete silence**.

**When adding a new AgentChatMessage creation, ALWAYS set `tenant_id`.** Check both the user message AND the assistant/reply message.

### 2. Non-reply messages via `owner_reply=False`

When the sidecar sends `owner_reply=False` but the message is from the owner's number, the server still routes to `_handle_owner_coach_whatsapp` via the `is_owner` check. This covers the case where the owner sends a NEW message (not replying to an existing one).

### Sidecar `isFromMe` behavior

With `emitOwnEvents: true` (current), owner replies from the phone arrive as `isFromMe: true`. The sidecar constructs the webhook payload with `owner_reply: true` and POSTs to the server. The echo filter (`sentMsgIds` Set) excludes messages the sidecar sent itself.

**Without `emitOwnEvents: true`**, owner replies are silently dropped by Baileys — the event never fires. This is the most common cause of "I replied on WhatsApp and got nothing." Always pair `emitOwnEvents: true` with the `sentMsgIds` echo filter (see `whatsapp-integration` skill).

### 4. DB Session Isolation

The webhook handler creates its own `db = init_db()` session. This session is separate from the FastAPI `get_db()` dependency injection used by the agent chat endpoint. Make sure both sessions can commit independently — a rollback in one doesn't affect the other.
