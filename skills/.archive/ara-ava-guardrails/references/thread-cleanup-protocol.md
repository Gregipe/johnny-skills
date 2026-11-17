# Thread Cleanup Protocol — Surgical DB Deletion

## When to Use

When the coaching thread is contaminated by:
- Names/concepts from past deals that keep getting proposed unsolicited
- Hallucinated tool failure messages that poison future turns
- Old confirmation proposals that confuse the LLM about what's actually pending
- Any assistant message that dominates attention weight and causes context collapse

## The Protocol

### 1. Identify the coaching thread

```python
import sqlite3
db = sqlite3.connect("/opt/ara/ara.db")
thread = db.execute("""
    SELECT id FROM chat_threads 
    WHERE tenant_id='3e736242' AND thread_type='coaching' 
    ORDER BY updated_at DESC LIMIT 1
""").fetchone()
tid = thread[0]
```

### 2. Dump the last N messages to find contamination

```python
msgs = db.execute("""
    SELECT role, substr(content,1,200), created_at, id 
    FROM agent_chat_messages 
    WHERE thread_id=? 
    ORDER BY created_at DESC LIMIT 30
""", (tid,)).fetchall()
msgs.reverse()
for m in msgs:
    print(f"[{m[2]}] {m[0]:10s} id={m[3][:8]} | {m[1][:180]}")
```

### 3. Identify contaminated messages

Look for:
- **Capability-dump contamination:** Assistant messages containing "Here's what I can do", "Here's what I bring", "Pipeline & CRM", "Leads & Contacts", "I can create/update", "I handle" — these prime the LLM to list capabilities on every greeting
- **Name/concept contamination:** Assistant messages containing a specific entity name (company, person) that's irrelevant to the current conversation
- **Hallucinated failures:** Assistant messages claiming a tool failed when no tool was actually called
- **Stale proposals:** Old `⏳ Confirm?` messages from previous sessions
- **Tool error noise:** Messages containing `ToolResult.fail`, `search_conversation_history` errors, etc.
- **Pattern:** `%Pipeline &%`, `%Here's what I%`, `%Here is what I%`, `%I can create%`, `%Leads &%`

### 4. Delete surgically

**Rule: Delete ONLY assistant messages, NEVER user messages.** User messages are Greg's actual conversation — deleting them removes context he intentionally provided.

```python
# Pattern 1: Delete by content pattern
db.execute("""
    DELETE FROM agent_chat_messages 
    WHERE thread_id=? 
      AND role='assistant' 
      AND content LIKE '%contaminated_pattern%'
""", (tid,))

# Pattern 2: Delete specific messages by ID
contaminated_ids = ['id1', 'id2', 'id3']
placeholders = ','.join(['?'] * len(contaminated_ids))
db.execute(
    f"DELETE FROM agent_chat_messages WHERE id IN ({placeholders})", 
    contaminated_ids
)

db.commit()
```

### 5. Verify

```python
# Confirm no contamination remains
check = db.execute("""
    SELECT COUNT(*) FROM agent_chat_messages 
    WHERE thread_id=? AND content LIKE '%contaminated_pattern%'
""", (tid,)).fetchone()[0]
print(f"Remaining references: {check}")  # should be 0

# Show the clean thread
remaining = db.execute("""
    SELECT COUNT(*) FROM agent_chat_messages WHERE thread_id=?
""", (tid,)).fetchone()[0]
print(f"Total messages: {remaining}")
```

## Safety Rules

1. **Delete user messages WHEN orphaned** — if an assistant response was deleted for contamination and the user message that triggered it remains, delete BOTH. Orphaned user messages (without a matching assistant response) create context gaps the LLM tries to fill.
2. **Use specific LIKE patterns** — `%Pipeline &%` or `%Here's what I can do%` not `%error%`
3. **Check what you're deleting first** — always run SELECT before DELETE
4. **Capability-dump contamination is real** — messages containing "Here's what I can do", "Here's what I bring", "Pipeline & CRM", "Leads &", etc. are contamination vectors. They prime the LLM to list capabilities on every subsequent greeting. Delete them aggressively.
5. **When contamination is deep (90+ messages of priming), archive the thread.** Create a fresh coaching thread and update the active reference. Don't keep cleaning incrementally — it takes too many cycles and misses patterns.

## Thread Archiving (When Incremental Cleanup Fails)

```python
import sqlite3, uuid
db = sqlite3.connect('/opt/ara/ara.db')
# Archive contaminated thread
db.execute("UPDATE chat_threads SET thread_type='archived' WHERE id='OLD_TID'")
# Create fresh thread
new_tid = uuid.uuid4().hex[:8]
db.execute("INSERT INTO chat_threads (id, tenant_id, title, thread_type, created_at, updated_at) VALUES (?, '3e736242', 'Coaching', 'coaching', datetime('now'), datetime('now'))", (new_tid,))
db.commit()
print(f'New coaching thread: {new_tid}')
```

## Jun 17 Case Study: Capability-Dump Contamination

**Problem:** "Hi Ava" → "Here's what I can do: Pipeline & CRM, Leads & Contacts..." — every greeting returned a capability list even with correct system prompt.

**Root cause:** 90+ messages in thread 80123f1c with capability-dump responses. The LLM loaded 50 of them and followed the learned pattern. Fresh thread with zero history: "Hi" → "Evening, Greg. How's the day treating you?" ✓

**Fix:** Archived thread 80123f1c, created fresh thread 1a082b68. System prompt was never the problem — thread history contamination was.

## Shriram Finance Case Study (June 17, 2026)

**Before cleanup:** 88 messages, 14 Shriram-contaminated assistant messages
**After cleanup:** 70 messages, 0 Shriram references in assistant messages
**Result:** Thread context clean — LLM no longer fixated on a deal from yesterday

Also cleaned: 3 junk messages (failed `search_conversation_history`, "Fair catch" noise), 1 wrong-cancellation message ("Okay, cancelled")

## Server Restart

After cleanup, restart the server so the next inbound message loads the clean thread:
```bash
systemctl kill ara-server && sleep 2 && systemctl start ara-server
```
