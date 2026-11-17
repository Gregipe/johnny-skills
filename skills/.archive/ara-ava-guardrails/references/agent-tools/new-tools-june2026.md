# New Tools Added (June 2026)

## list_documents
Lists all documents in the knowledge base, categorized by type:
- 📊 Deck — PDF pitch decks, white papers
- 🌐 Site — website scrapes
- 📝 Doc — text files, notes

**Args:** none
**Read-only:** yes
**Location:** server.py, in execute_tool()

## send_attachment
Sends a document from the knowledge base to a lead via WhatsApp or email.

**Args:**
- lead_name (required) — who to send to
- filename (required) — document filename (fuzzy match)
- caption (optional) — message to include
- channel (optional) — "whatsapp" or "email", defaults to whatsapp

**Read-only:** no — creates ScheduledAction
**Location:** server.py, in execute_tool()

## eval_meeting
Evaluates a meeting transcript using Scribe v2 + the eval agent prompt. Extracts summary, action items, lead notes, quality flags.

**Args:**
- transcript (required) — full conversation text (min 20 chars)

**Read-only:** yes — only extracts, does not write to CRM
**Location:** server.py, in execute_tool()
**Prompt:** /opt/ara/eval_agent_prompt.py

## Tool definitions
All tools must be added to both:
1. `execute_tool()` handler (server.py ~line 3967)
2. Tool schema dict (server.py ~line 5939)

Also update `data_modifying_tools` set at line ~5081 if the tool is a mutation tool.
