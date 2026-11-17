# Inbound Message Webhook: Baileys → Python

The Baileys sidecar receives inbound messages via its WebSocket `messages.upsert` event. These must be forwarded to the Python server so they can be logged, trigger stage changes, cancel cadences, and fire Ava auto-responses.

## Architecture

```
Inbound WhatsApp message
  → Baileys sock.ev.on('messages.upsert')
    → Sidecar extracts: phone (from JID), pushName, message text
      → HTTP POST to Python server's /api/whatsapp/inbound
        → _handle_inbound_whatsapp(phone, name, message)
          → Logs Conversation (direction=inbound)
          → Lead stage: reached_out → engaged (if first reply)
          → Lead.first_reply_at set
          → Cancels ALL pending scheduled actions for that lead
          → If lead.assigned_agent == "ava": generates + sends auto-response
```

## Filtering

| Type | Filter | Action |
|------|--------|--------|
| Lead replies | `!msg.key.fromMe` | Forwarded to `_handle_inbound_whatsapp` (stage change, cadence stop, auto-response) |
| Owner replies | `msg.key.fromMe` | Forwarded with `owner_reply: true` flag to `_log_owner_reply` (log only, no stage change) |
| Group chats | `remoteJid.endsWith('@g.us')` | Skipped — not lead messages |
| Status broadcasts | `remoteJid.endsWith('@broadcast')` | Skipped — not lead messages |
| Non-text | No `conversation`/`extendedTextMessage.text` | Skipped — reactions, images, voice notes |

## Owner Reply Handling

The sidecar is authenticated as the **owner's** WhatsApp account. When the owner replies to a lead's conversation on their phone, the message has `fromMe: true`. The sidecar must NOT skip these — instead, it sends them with `owner_reply: true` to the Python webhook.

The Python webhook routes to `_log_owner_reply`, which:
1. Finds the lead by phone number (or falls back — see below)
2. Creates a Conversation with `direction="outbound"` and subject `"Owner reply to {name}"`
3. Updates `lead.last_contacted_at`
4. **If lead is assigned to Ava**, calls `_ava_auto_respond()` so Ava generates a contextual reply to continue the conversation
5. Does NOT change stage or cancel cadences

### JID Format: `@s.whatsapp.net` vs `@lid`

WhatsApp uses two JID (Jabber ID) formats for direct messages:

| Format | Example | When |
|--------|---------|------|
| `@s.whatsapp.net` | `919582549236@s.whatsapp.net` | Regular phone number — messages between different users |
| `@lid` | `37039848317007@lid` | LID (Linked ID) — self-chats, messages to own number, some multi-device scenarios |

**Impact on phone extraction**: The sidecar extracts phone numbers from `remoteJid` like this:
```javascript
const phone = remoteJid.replace('@s.whatsapp.net', '').replace(/[^0-9]/g, '');
```

This ONLY works for `@s.whatsapp.net` JIDs. For `@lid` JIDs, the replacement does nothing and the extracted string is gibberish (`37039848317007` instead of `919582549236`). Consequently, `_log_owner_reply` cannot find the lead by phone.

**Detection in logs**: The sidecar logs the full JID when `isFromMe=true`. Look for `@lid` in the log:
```
Owner reply to JID 37039848317007@lid (Greg): "..."
```

### Phone Fallback for Owner Replies

**Critical edge case**: When the owner tests the system with their OWN phone number as the lead, or when the `remoteJid` is a `@lid` JID (self-chat), the phone extracted from the JID won't match any lead's phone number in the database.

Example: Lead (Gregory Ipe) has phone `9582549236`, which is also the owner's phone. When the owner replies to the self-chat on WhatsApp, the `remoteJid` is `37039848317007@lid` — neither a phone number nor any other identifiable value.

**Fix**: When phone lookup fails, fall back to the most recent lead Ava messaged on WhatsApp:

```python
if not lead:
    recent_conv = db.query(Conversation).filter(
        Conversation.channel == "whatsapp",
        Conversation.direction == "outbound",
        Conversation.lead_id.isnot(None),
    ).order_by(Conversation.created_at.desc()).first()
    if recent_conv and recent_conv.lead_id:
        lead = db.query(Lead).filter(Lead.id == recent_conv.lead_id).first()
```

**Important**: Do NOT filter by `conversation.subject.like("Ava%")` — subjects are typically `"Outbound cadence to {name}"` or `"Owner reply to {name}"`, none of which start with "Ava". Use the broader filter above which matches any WhatsApp outbound conversation.

This relies on the assumption that the owner is replying in the most recent WhatsApp conversation, which is the most frequent scenario during testing.

### `AVA_AUTO_SYSTEM_PROMPT` Format String Pitfall

The prompt template string has JSON-like example content inside it:
```
- payload: {"message": "Your follow-up message here"}
```

In Python `str.format()`, curly braces `{message}` are interpreted as format placeholders. Since `message` is NOT among the format parameters passed (the parameter is `lead_message`), this raises a `KeyError: 'message'`.

**Fix**: Escape the inner braces with doubled braces:
```
- payload: {{"message": "Your follow-up message here"}}
```

### Owner Auto-Response

After `_log_owner_reply` logs the owner's message, if the lead is assigned to Ava, it calls:

```python
_ava_auto_respond(lead, message, TENANT_ID, phone_clean, db, conv)
```

This loads the full conversation history (including the owner's latest message), generates a contextual response via LLM, and sends it from Ava to the lead. The flow:

```
Owner replies on WhatsApp
  -> _log_owner_reply (log owner message)
    -> _ava_auto_respond (Ava generates response)
      -> wa.send_message_sync (Ava sends to lead)
      -> Logs Ava's response as outbound
```

### CRITICAL: Use `lead.phone` not `phone_clean` for Auto-Response Send

When the lead was found via the phone fallback (not a direct phone match), the `phone_clean` parameter contains a garbage value extracted from an `@lid` JID. Using it as the target phone sends the auto-response to the wrong number.

**Wrong:**
```python
send_result = wa.send_message_sync(phone_clean or lead.phone, response)
# phone_clean is "9848317007" (garbage) — message goes nowhere
```

**Correct:**
```python
send_result = wa.send_message_sync(lead.phone or phone_clean, response)
# lead.phone is "9582549236" — message reaches the right person
```

**Rule of thumb:** When a lead exists in the database, `lead.phone` is always more reliable than an extracted phone from a JID. Prefer `lead.phone` for any send call.

### Stage Update After Auto-Response

After Ava successfully sends an auto-response (whether triggered by a lead reply or an owner reply), the lead's stage should advance:

```python
if lead.stage in ("new", "reached_out"):
    lead.stage = "engaged"
    lead.updated_at = utcnow()
    db.commit()
```

This is done inside `_ava_auto_respond` after logging the outbound conversation. Without this, a lead that the owner engaged with stays at `reached_out` even though Ava has re-engaged them.

## Auto-Response Pipeline

Auto-response is a **shared function** called from both `_handle_inbound_whatsapp` (lead replies) and `_log_owner_reply` (owner replies):

```python
def _ava_auto_respond(lead, lead_message, tenant_id, phone_clean, db, conv):
    # Loads recent conversation history (last 6 messages)
    # Loads skills context from learning flywheel
    # Builds prompt from AVA_AUTO_SYSTEM_PROMPT template
    # Calls LLM via induction_engine.call_llm
    # Sends via wa.send_message_sync
    # Logs outbound conversation
    # Fires learning analysis on background thread
```

The prompt template (`AVA_AUTO_SYSTEM_PROMPT`) is generic -- it doesn't hardcode "INBOUND message from a lead" because it's also used for owner reply contexts. Instead it says "responding to a message from or regarding {lead_name}".

## Auto-Response Send Result Bug

The BaileysWA client returns `{"status": "sent", "msg_id": "..."}` on success. The auto-response code at `_handle_inbound_whatsapp` around line 4955 historically checked:

```python
send_result = wa.send_message_sync(phone, response)
if send_result.get("success"):  # BUG: 'success' is never in the response dict
```

This check is ALWAYS falsy because `success` is not a key in the sidecar client response. The response has `status` (not `success`). This means:
1. Ava generates a reply and sends it (the message goes through)
2. But the outbound Conversation is NEVER logged
3. The learning analysis thread is never started
4. Next time Ava checks the conversation history, the auto-response is invisible

Fix:
```python
if send_result.get("status") == "sent" or "msg_id" in send_result:
```

## SyncFullHistory

With `syncFullHistory: false` (default), Baileys does NOT fetch past messages when reconnecting. Set to `true` to trigger a history sync on reconnect. Note: WhatsApp's history sync has a ~30s timeout; after timeout Baileys transitions to Online and logs `"Timeout in AwaitingInitialSync, forcing state to Online and flushing buffer"`. Recent messages are still received going forward.
