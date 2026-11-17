# Action Listing Format & Task Execution Behavior (June 16, 2026)

## 1. Action Listing Format Directive

**Problem:** Ava responded to "what's pending?" in two different sessions with two different formats:
1. Clean bullet points (first session) — exactly what Greg wanted
2. Raw tool-call-like output: `✅ Get Action Items 📋 Action Items (open): • [open] Send Infosec...` (second session) — Greg hated this

**Why the inconsistency:** No explicit formatting directive in the system prompt. The LLM sometimes rendered actions nicely, sometimes dumped the raw `_build_recent_actions_block` format.

**Fix (server.py ~line 5562, `_build_recent_actions_block` heading):**
```
When the user asks what is pending or what actions are open, format your reply like this:
• **Action title** — due Mon DD, H:MM AM/PM IST (Lead Name)
One per line. No brackets, no tool-call markers, no raw JSON. Just clean bullet points.
```

**Also:** Lead names are now injected into each action line (previously missing):
```python
lead_name = ""
if r.ref_id:
    lead = db.query(Lead).filter(Lead.id == r.ref_id).first()
    if lead:
        lead_name = f" for {lead.name}"
lines.append(f"{status} — {desc}{lead_name}{due_str}{age}")
```

## 2. Task Execution: Don't Show Investigation as Answer

**Problem:** Greg asked "send an email to Jimmie Tete with the company deck attached. If you have any questions, ask me." Ava responded with `get_lead_detail` + `list_documents` results — showing intermediate investigation as the final answer. She never asked for the deck or explained she can't attach files.

**Root cause:** The system prompt's "Do, don't investigate first" rule (Tool-Calling Principle #6) says call the data tool FIRST. But when the tool lacks capability (no attachment param on `send_email`), the LLM pre-investigated instead of executing, then presented investigation results as the answer.

**The behavior Greg wants:** When given a task Ava can't fully execute:
1. Identify what's missing (the deck, the email body, etc.)
2. Ask ONE clear question: "I don't have the company deck uploaded — could you share it? I have Jimmie's email as jimmytete@bajaj.com."
3. NEVER respond with unrelated data (lead details, empty document lists, health checks)
4. A "send email" request gets a response about email. A "what's pending" gets actions. Stay on intent.

**Proposed prompt addition (not yet deployed):**
> **When you hit a gap, say what you need — nothing else.** If the user asks for something a tool can't do (attachments, multi-step workflows, missing info), identify exactly what's missing and ask one clear question. Never respond with intermediate investigation results (lead details, document lists, health checks) when the user asked for an action. A "send the deck" request gets a response about the deck.

**Status:** Under discussion with Greg. Not yet in system prompt.
