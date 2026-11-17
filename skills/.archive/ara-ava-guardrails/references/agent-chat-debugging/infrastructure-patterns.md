# Infrastructure Patterns — Sidecar, Tools, Pending Actions (Jun 17, 2026)

## Sidecar Pending Message Replay

**Problem:** Messages sent during server downtime can be lost if not handled.

**Mechanism:** The WhatsApp sidecar persists every inbound self-chat message to `pending.json` BEFORE attempting to forward to the ARA server. If the POST fails (server down), the message stays in `pending.json`. On next SIDECAR restart, all pending messages are replayed.

```javascript
// In messages.upsert handler
addPending(phone, name, text, true, msg.key.id, remoteJid);  // persist first
const result = await sendToARA_promise(...);                  // then forward
if (result) removePendingByMsgId(msg.key.id);                 // success → remove
```

**Important:** Replay only happens on SIDECAR restart, not server restart. If the sidecar stays up but the server goes down and comes back, pending messages sit in `pending.json` until the next sidecar restart.

**Check pending queue:**
```bash
cat /opt/ara/whatsapp-sidecar/pending.json
```

**Force replay:**
```bash
systemctl restart ara-whatsapp-sidecar
```

**Sidecar reconnection message loss:** When the WhatsApp session resets (closing session for "incoming prekey bundle"), the sidecar can be down for 1-2 minutes. Messages sent during this window are NOT captured in `pending.json` because the sidecar isn't running to receive them. These are permanently lost.

## ToolResult.fail() Signature Bug (Fixed Jun 17, 2026)

**Bug:** `search_conversation_history` handler called `ToolResult.fail(tool, message)` with 2 args, but the signature requires 3: `ToolResult.fail(tool, code, message)`.

```python
# BROKEN (line 5224):
return ToolResult.fail("search_conversation_history", "No query provided...")
# FIXED:
return ToolResult.fail("search_conversation_history", "MISSING_ARG", "No query provided...")

# BROKEN (line 5243):
return ToolResult.fail("search_conversation_history", f"Search failed: {e}")
# FIXED:
return ToolResult.fail("search_conversation_history", "SEARCH_FAILED", f"Search failed: {e}")
```

**Check for more:** `grep -n 'ToolResult.fail(' server.py` — verify all calls have 3 positional args before keyword args.

## Stale Pending Action Cleanup

**Problem:** Old `awaiting_approval` ActionItems from previous sessions contaminate the confirmation flow. When a new message arrives, the classifier checks for live pending actions and may match against a stale one.

**Cleanup:**
```sql
-- Find stale pending
SELECT id, description, created_at FROM action_items 
WHERE execution_state='awaiting_approval' ORDER BY created_at DESC;

-- Cancel them
UPDATE action_items SET execution_state='cancelled', status='resolved', 
outcome_state='cancelled', resolved_at=datetime('now') 
WHERE execution_state='awaiting_approval' AND [contamination_pattern];
```

**Shriram Finance case:** 5 stale pending actions (48, 39, 17, 30, cc) all proposing "Ajay Fageria (Shriram Finance)" — each one created because the LLM hallucinated the same proposal on every ambiguous message. All cancelled in the session cleanup.

## Pipeline Deletion for Persistent Contamination

When a lead/deal name keeps appearing in hallucinations despite clean thread history and zero pending actions, the pipeline injection itself is the source. The entity exists in the DB and appears in every turn's pipeline section.

**Delete from DB:**
```sql
DELETE FROM deals WHERE id='...';  -- or org_name LIKE '%pattern%'
DELETE FROM leads WHERE id='...';  -- or name LIKE '%pattern%'
DELETE FROM action_items WHERE description LIKE '%pattern%';
```

**Verification:** Confirm zero references remain in leads, deals, action_items, and agent_chat_messages tables.
