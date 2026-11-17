# Confirmation Flow Pitfalls (June 2026)

## 1. pre_confirmed overrides voice_note safeguard

**Location:** `_run_observe_loop()` in server.py (lines 5269-5273)

**Bug:** Voice notes MUST always require confirmation (`[ACTION: ASK]`) for data-modifying tools. But the order of checks was:
1. `if voice_note: intent = "ask"` (line 5269)
2. `if pre_confirmed: intent = "now"; confirmed = True` (line 5272)

Line 5272 runs AFTER and overwrites the voice note safeguard. The LLM outputs `[ACTION: NOW]` → `pre_confirmed=True` → voice note protection is silently defeated.

**Fix:** Reorder so voice_note check runs LAST:
```python
if pre_confirmed:
    confirmed = True
    intent = "now"

# Voice notes ALWAYS force confirmation — run AFTER pre_confirmed
if voice_note and is_data_modifying:
    intent = "ask"
    confirmed = False
```

**Symptom:** Voice note email sends immediately without asking the user to confirm.

## 2. send_email attachment: two-part architecture

The flow has two independent stages that must stay in sync:

### Stage 1: Tool handler stores attachment metadata
**Location:** `execute_tool` → `send_email` branch (line 4325)

```python
attachment = args.get('attachment', '')  # filename from LLM
# Fuzzy-match in documents table
doc = db.query(Document).filter(
    Document.filename.ilike(f"%{attachment}%")
).first()
# Store in payload
payload = {'subject': subject, 'body': body, 'attachment': doc.filename}
```

### Stage 2: Scheduler loads and attaches the file
**Location:** `_execute_action` → legacy dispatch (line 8063)

```python
attachment_filename = payload.get("attachment", "")
# Find document, load from disk
doc = db.query(Document).filter(
    Document.filename.ilike(f"%{attachment_filename}%")
).first()
filepath = os.path.join(UPLOAD_DIR, doc.id + "_" + doc.filename)
with open(filepath, "rb") as f:
    attachments = [(doc.filename, f.read())]
# Pass to Gmail API
send_via_gmail_api(tokens, email, subject, body, attachments=attachments)
```

**Critical:** Both stages must match on filename lookup. Stage 2 adds `os.path.join(UPLOAD_DIR, doc.id + "_" + doc.filename)` — if the file doesn't exist on disk, attachment is silently skipped (logged as warning).

## 3. PENDING_TTL and channel latency

The confirmation window (`PENDING_TTL`) was 120 seconds. Voice notes take 20-30s to transcribe, process, and generate a proposal. The user then needs time to read and reply. 120s was too tight — proposals expired before "yes" arrived.

**Fix:** Bumped to 600 seconds (10 minutes). **Rule:** The slowest channel (voice notes on mobile) dictates the minimum TTL.

**When the TTL expires:** The pending action is marked `cancelled`. The user's next message hits `live-pending: NONE` and the LLM treats it as a fresh command — often hallucinating an unrelated action (e.g., Daily Summary cron).

## 4. Confirmation prompts must be explicit questions

`_build_pending_description()` generates the proposal text shown to the user. Before June 2026, all prompts were declarative statements:
```
Send email to Jimmie Tete: Hunar.ai Company Deck
```
This doesn't ask for confirmation — it sounds like the action is already happening.

**Fix:** Every prompt now ends with an explicit question:
```
📧 Send email to Jimmie Tete — shall I send it?
💬 Send WhatsApp to Rajesh — shall I send it?
📋 Create action: Call Him — shall I create it?
```

**System prompt enforcement (updated June 18, 2026):**
> [ACTION: ASK] — propose and WAIT for the user to respond. This is a BLOCKING step — nothing happens until the user replies. Your message MUST be an explicit question ending with "?" that the user can answer "yes" or "no" to. Use "shall I...?" or "want me to...?" at the end. Never make a declarative statement — if it doesn't end with "?", the user won't know to respond. Example: "📧 Send email to Jimmie Tete with subject X — shall I send it?" NOT "Sending email to Jimmie Tete." NOT "Email ready for Jimmie Tete."

**Confirmation wrapper (updated June 18, 2026):**
> ⏳ Waiting for you — reply yes to confirm or no to cancel:
(was: "⏳ Confirm? Reply yes/send to proceed:" — "reply yes/send" was ambiguous)

## 5. Document upload: two tiers

| Method | What it stores | Email attachment? |
|--------|---------------|-------------------|
| Chat `upload_document` tool | `text_content` in `documents` table | ❌ No file on disk |
| Dashboard upload (`/api/knowledge/upload`) | Binary file at `UPLOAD_DIR/{id}_{filename}` + DB record | ✅ Yes |

`list_documents` returns records from both paths but doesn't distinguish sources. LLM may see filenames from chat uploads and assume attachable files exist. **Include source info in `list_documents` response** so the LLM knows which are real files.

## 6. Classifier must handle status-check confirmations (June 18, 2026)

**Bug:** User asks "Done ?" or "ok - update on the actions ?" after a confirmation proposal. The `_classify_confirmation()` LLM call classified these as `"unrelated"` — so instead of executing the pending confirmation, a NEW duplicate confirmation was created with the same tool calls. This caused a stall loop: 3 identical pending confirmations, zero actions executed.

**Root cause:** The classifier prompt only listed explicit affirmatives:
```
"A short affirmative answering the proposal (\"yes\", \"set it\", \"go ahead\", \"do it\") => confirm\n"
```

Status-check questions ("Done?", "Update?", "What happened?") IMPLY the user expected execution — they're asking about the result because they thought it was happening.

**Fix (June 18, 2026):** Added explicit rules for status-check confirmations:
```
"- A status check that implies the proposal was expected to execute " + 
"(\"done?\", \"is it done?\", \"update?\", \"any update?\", \"what happened?\", \"did you do it?\") => confirm " +
"— the user is asking because they expected you to proceed\n"
```

Also added more explicit affirmative examples: `"ok"`, `"sure"`, `"perfect"`.

**Pitfall:** Status-check questions are the most common false-negative pattern. When the LLM's proposal text reads like execution (e.g., "Let me create them all now" — a statement, not a question), the user assumes it's happening and checks status. The classifier must recognize this as confirmation intent.
