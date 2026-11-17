# search_conversation_history Tool — June 17, 2026

## What
FTS5-backed conversation search tool for Ava. Lets her search past conversations (across all channels — dashboard, WhatsApp, Telegram) for context when Greg references something discussed earlier.

## Architecture

**FTS5 Index:** Virtual table `agent_chat_messages_fts` on `agent_chat_messages.content` with auto-sync triggers (INSERT/UPDATE/DELETE).

```sql
CREATE VIRTUAL TABLE agent_chat_messages_fts USING fts5(
    content,
    content='agent_chat_messages',
    content_rowid='rowid'
);
```

**Tool Schema:**
```python
"search_conversation_history": {
    "description": "Search past conversations with Greg for context...",
    "read_only": True
}
```

**Handler pattern:**
```python
elif tool_name == "search_conversation_history":
    query = args.get("query", "")
    _rows = _cdb.execute(
        "SELECT content, created_at FROM agent_chat_messages_fts WHERE ... MATCH ? ORDER BY rank LIMIT ?",
        (query, limit)
    ).fetchall()
    return ToolResult.ok(search=query, result="\n\n".join(snippets), count=len(_rows))
```

## How It's Wired

1. **FTS index** on `agent_chat_messages` with auto-sync triggers
2. **Tool schema** registered in `TOOL_SCHEMAS` dict in server.py
3. **Handler** in `execute_tool()` function
4. **Prompt rule** in AGENT_SYSTEM_PROMPT_BASE: "Search before you guess"

## When Ava Uses It

The prompt rule triggers when Greg references something vaguely and the injected thread context (last 10 messages) doesn't make the referent obvious. Ava searches before answering instead of guessing.

Example: Greg asks "what tool were we discussing?" → thread context is empty (new session) → Ava calls `search_conversation_history(query="tool")` → finds `import_leads_from_text` discussion → answers correctly.

## Pitfall: Schema Without Handler

The schema entry was added first but the handler was forgotten. The LLM sees the tool in the schema, tries to call it, and gets a generic error because no `elif` branch matches. Always verify: `grep -n "elif tool_name == \"search_conversation_history\":" server.py`.
