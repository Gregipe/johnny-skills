# Conversation History Search Tool

**Tool:** `search_conversation_history`
**Added:** June 17, 2026
**Purpose:** Let Ava search past conversations for context before responding.

## Problem It Solves

Ava loses context between turns. If Greg asks \"does that tool support notes?\", Ava doesn't know \"that tool\" refers to `import_leads_from_text` because each turn starts fresh with only the system prompt. No conversation history is injected.

## Architecture

- **FTS5 virtual table** on `agent_chat_messages.content` with auto-sync triggers (INSERT, UPDATE, DELETE)
- **Tool schema** registered in `TOOL_SCHEMAS` dict at `/api/agent_chat`
- **Handler** in `execute_tool` block (server.py ~line 5186)
- **Parameters:** `{\"query\": \"search terms\", \"limit\": 5}`
- **Returns:** Matching message snippets with timestamps, sorted by relevance

## FTS5 Index Setup

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS agent_chat_messages_fts USING fts5(
    content,
    content='agent_chat_messages',
    content_rowid='rowid'
);

-- Rebuild to catch existing data on first install:
INSERT INTO agent_chat_messages_fts(agent_chat_messages_fts) VALUES('rebuild');
```

Triggers keep the index in sync on INSERT/UPDATE/DELETE.

## When Ava Should Use It

- Greg references \"the tool we just discussed\" → search for tool name
- Greg says \"you mentioned...\" → search for the topic
- Greg asks about something from earlier in the conversation
- Follow-up questions where context is implied

## How It Fits Into The Larger Context Strategy

This is layer 1 of a multi-layer approach:
1. **search_conversation_history** — just-in-time retrieval (this tool)
2. **Daily digest** — compressed summary of day's conversation (future)
3. **Stale context breadcrumbs** — 1-line reminders of past 24h topics (future)
4. **Full session injection** — for session-based interfaces (future)

The pattern is: search when you need context, don't pre-load it.
