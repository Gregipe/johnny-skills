# Confirmation Prompts, Execution Confirmations & Gap Handling — June 16, 2026

Session summary of prompt and tool changes made to improve Ava's communication clarity.

## 1. Confirmation Prompts As Questions

**Problem:** Pending confirmation prompts read as declarative statements ("Send email to Jimmie Tete: Subject"), not questions. Users didn't realize they needed to respond "yes."

**Fix — `_build_pending_description` (server.py ~line 5431):** All confirmation prompts now end with `— shall I...?`:

```
📧 Send email to Jimmie Tete — shall I send it?
💬 Send WhatsApp to Rajesh — shall I send it?
📋 Create action: Call Him — shall I create it?
⏰ Set reminder: Send pricing — shall I set it?
🔄 Schedule: Daily Summary (daily at 18:30) — shall I set it up?
➕ Add lead: John Doe (Acme) — shall I create it?
✏️ Update Jimmie Tete: email, phone — shall I update it?
📊 Move Rajesh to engaged — shall I move it?
💰 Create deal: Acme Corp — shall I create it?
🚀 Start cadence for Rajesh — shall I start it?
🚨 Escalate: Urgent issue — shall I escalate?
❌ Cancel scheduled: action_id — shall I cancel it?
```

Each prompt includes an emoji prefix, the action, the target, and an explicit question.

## 2. Post-Execution Confirmation Clarity

**Problem:** When a tool succeeded, Ava just said "Done" or "Sent" with no detail.

**Fix — System Prompt Rule #7:** Changed from "confirm plainly and stop" to:

> **7. Use what the tool returns.** After a tool runs you'll be shown its result. On success: confirm clearly — state what was done, to whom, and when. For example: "✅ Email sent to Jimmie Tete (jimmytete@bajaj.com) at 6:15 PM IST." Don't just say "Done."

Also updated `send_email` tool return to include timestamp and attachment info:

```python
now_ist = (utcnow() + timedelta(hours=5, minutes=30)).strftime('%I:%M %p')
att_text = f" with {attachment}" if attachment else ""
return f"✅ Email queued for {lead.name} ({lead.email}){att_text} at {now_ist} IST. Subject: {subject}"
```

## 3. Gap Handling — Ask, Don't Investigate

**Problem:** When Ava couldn't execute a request (missing attachment, unknown lead), she dumped intermediate investigation results (lead details, empty doc lists) instead of asking a clarifying question.

**Fix — New System Prompt Rule #9:**

> **9. When you hit a gap, ask — don't investigate.** If the user asks for something you can't fully execute (missing attachment, unknown lead, ambiguous request), identify exactly what's missing and ask one clear question. Never respond with intermediate investigation results (lead details, document lists, health checks) when the user asked for an ACTION. A "send the deck" request gets a response about the deck. A "what's pending" request gets actions. Stay on the user's intent — if you need something to proceed, ask for it directly.

## 4. [ACTION: ASK] Must Be A Question

**Problem:** The Execution Intent Protocol said "propose and wait" but didn't enforce question format. LLMs wrote declarative proposals that users read as statements of completion.

**Fix — Execution Intent Protocol updated:**

```
- [ACTION: ASK] — propose and wait. Write your message as a clear question ending 
  with "shall I...?" or "want me to...?" — never a declarative statement. 
  Example: "📧 Send email to Jimmie Tete — shall I send it?" 
  NOT "Send email to Jimmie Tete."
```

## 5. Email Attachment Support

**Feature:** `send_email` now accepts `attachment: "filename.pdf"`. The tool looks up the filename in the Documents table (exact match first, then fuzzy ILIKE). If found, the filename is included in the ScheduledAction payload.

**Tool schema updated:**
```
"send_email": {"description": "-- Send email to lead. Use attachment param to reference 
a file from the knowledge base (call list_documents first to find the filename). 
DO NOT call this when user says \"update\" or \"move\" stage. 
Args: {\"lead_name\": \"...\", \"subject\": \"...\", \"body\": \"...\", 
\"attachment\": \"filename.pdf\"}", "read_only": False},
```

**Implementation detail:** The Document model has `filename` (not `file_path`). The attachment is stored by filename reference. The actual file serving/attaching is handled by the email sender in the scheduler's `_execute_action`.

## 6. Action Listing Format

**Problem:** Ava sometimes showed actions in raw tool-call format instead of clean bullet points.

**Fix — `_build_recent_actions_block` heading updated** with explicit format instruction:
```
When the user asks what is pending or what actions are open, format your reply like this:
• **Action title** — due Mon DD, H:MM AM/PM IST (Lead Name)
One per line. No brackets, no tool-call markers, no raw JSON. Just clean bullet points.
```

Also added lead name resolution to each action line (looks up lead by `ref_id`).

## 7. Email Attachment Actually Attached — Dispatch Fix

**Problem:** The `send_email` tool correctly stored `attachment: "filename.pdf"` in the ScheduledAction payload. But the scheduler's `_execute_action` legacy email dispatch (line ~8063) called `send_via_gmail_api(tokens, email, subject, body)` — NO attachment parameter. The email went without the file even though the payload had it.

**Fix — `_execute_action` legacy email dispatch (commit `bc7f684`):** Reads `payload.attachment`, looks up the Document record by fuzzy filename match, reconstructs the file path (`UPLOAD_DIR/{doc_id}_{filename}`), loads the file bytes, and passes `attachments=[(filename, bytes)]` to `send_via_gmail_api`:

```python
attachment_filename = payload.get("attachment", "")
if attachment_filename:
    doc = db.query(Document).filter(
        Document.tenant_id == action.tenant_id,
        Document.filename.ilike(f"%{attachment_filename}%"),
    ).first()
    if doc:
        filepath = os.path.join(UPLOAD_DIR, doc.id + "_" + doc.filename)
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                attachments = [(doc.filename, f.read())]
success, err_msg = send_via_gmail_api(tokens, lead.email, subject, body, attachments=attachments)
```

**Key detail:** `send_via_gmail_api` already supported `attachments: list[tuple[str, bytes]]`. The gap was only in the dispatcher, not the email utility.

## 8. SQL NULL Comparison Pitfall

**Problem:** The `GET /api/actions` filter was `ActionItem.outcome_state != "resolved"`. In SQL, `NULL != 'resolved'` evaluates to `NULL` (not `TRUE`), and SQL WHERE clauses treat NULL as false. Every action with `outcome_state IS NULL` was excluded — returning 0 results even when valid pending actions existed.

**Fix:** Simplified the filter to only exclude cancelled: `ActionItem.execution_state != "cancelled"`. The frontend handles resoved/history actions via its own tab filtering.

**Pitfall rule:** Any SQLAlchemy filter with `!= "string"` will silently exclude NULL rows. When filtering on nullable columns, always add an explicit `OR column IS NULL` clause:

```python
# ❌ BROKEN — NULL rows excluded
q.filter(Model.status != "resolved")

# ✅ CORRECT — NULL rows included
from sqlalchemy import or_
q.filter(or_(Model.status != "resolved", Model.status == None))
```

## Files Changed

- `server.py`: `_build_pending_description`, `AGENT_SYSTEM_PROMPT_BASE` Rules 7-9, Execution Intent Protocol, `send_email` tool handler + schema, `_build_recent_actions_block`, `_execute_action` email dispatch, `GET /api/actions` filter
- Commits: `faf5015`, `bc7f684`
