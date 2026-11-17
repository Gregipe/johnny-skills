# Web Search Mandate (June 8, 2026)

## Problem

When Greg asked Ava to search the internet for the latest news on Shadowfax (a logistics company), Ava hallucinated information about "Acme Manufacturing" — a completely made-up company. She did not call `web_search` at all.

Root cause: The `web_search` tool was documented in the system prompt's tool schema and listed as "read-only, call freely," but there was no **mandatory directive** forcing its use for search requests. The Tool-First Policy section only mandated `search_knowledge_base`. Ava treated "web search" as optional.

## Fix — Two Changes in `server.py`

### 1. Tool-First Policy (AGENT_SYSTEM_PROMPT_BASE, ~line 4896)

Added right after the `search_knowledge_base` mandate:

```
You MUST call **web_search** when Greg asks you to search the internet, look up
something online, find news, or any similar request. Output [TOOL_CALL: {"tool":
"web_search", "args": {"query": "..."}}] and STOP. Wait for the result. Do NOT
make up search results. If you do not have the information from a tool call, say so.
```

### 2. Data Honesty Section (~line 4954)

Added after the "do not frame successful actions as errors" line:

```
**CRITICAL: Never invent or fabricate search results, company names, or news.**
If Greg asks you to search for something and you did not call web_search, do not
pretend you found results. Say "Let me search for that" and call web_search.
```

## Why This Works

The `web_search` tool itself works correctly — it uses Tavily (primary) with DuckDuckGo fallback and returns real web results:

```python
# server.py, ~line 3590
def web_search(query, max_results=5, tenant_id=None):
    api_key = resolve_api_key("tavily", tenant_id)
    result, err = _search_tavily(query, max_results, api_key)
    if err:
        result = _search_ddg(query, max_results)
    return result
```

The problem was purely prompt engineering: the tool existed, the LLM knew about it, but it wasn't **forced** to use it. The mandate pattern (from the proven KB mandate) fixes this.

## Pattern

When Ava consistently ignores a tool that would solve her hallucination problem:

1. Don't add more text to the tool schema — she sees that but doesn't treat it as an instruction
2. Add a **mandatory directive** in the relevant behavioral section (Tool-First Policy for action tools, Data Honesty for truthfulness)
3. Use the same "You MUST call..." / "Do NOT..." pattern as the KB mandate
4. Layer: instruction in behavioral section + consequence warning in Data Honesty

## Verified

- `web_search("Shadowfax logistics latest news 2026")` returns real Tracxn acquisition data and PitchBook profile — works from the server
- The mandate text was tested by patching server.py and restarting the server
- Both the web_search and anti-fabrication instructions were pushed to GitHub (commit `55f5f8c`)
