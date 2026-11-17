# Ava Tool Additions — June 2026 Batch

Six new tools added in a single session. All follow the standard [TOOL_CALL] pattern.

## Tool List

### `check_health` (tool #42) — Read-only, no confirmation
Checks all system services at once and returns a clean status:
- **WhatsApp**: connected/disconnected (via `wa.status_sync()`)
- **Gmail**: authenticated/not configured (via `db.query(IntegrationConfig)`)
- **Tavily**: API key present/missing (via `resolve_api_key("tavily", tenant_id)`)
- **Sidecar**: online/offline (via HTTP to `localhost:8767/health`)

No args needed.

### `query_leads` (tool #43) — Read-only, no confirmation
Two modes:
- **Filtered list**: `{"filters": {"segment": "logistics", "stage": "reached_out"}}` → matching leads with count
- **Breakdown**: `{"filters": {}, "group_by": "segment"}` → grouped counts with percentages per segment
- Group by options: `segment`, `stage`, `source`, `industry`
- Filters: `segment`, `stage`, `source`, `industry`, `city`

### `list_documents` (tool #44) — Read-only, no confirmation
Returns all uploaded knowledge base documents with title, word count, upload date.
Optional `source` filter (e.g. `"kb"`).

### `upload_document` (tool #45) — Data-modifying, needs confirmation
Saves text content to the knowledge base. Args: `title`, `content`, `source` (default: "ava").
Content becomes available for induction and system prompt context immediately.

### `add_to_watchlist` (tool #46) — Data-modifying, needs confirmation
Queues an item for the next coaching conversation. Args:
- `category`: "contradiction", "new_learning", "ambiguity", "question", "suggestion"
- `description`: the watchlist item text
- `source_ref`: optional lead/conversation reference

Does NOT ping the owner — item sits in the watchlist until the next coaching conversation
or the daily catch-up.

### `resolve_watchlist_item` (tool #47) — Data-modifying, needs confirmation
Marks a watchlist item as resolved/dismissed. Args:
- `item_id`: the watchlist item ID
- `resolution`: "applied", "dismissed", "skip"
- `notes`: optional resolution notes

## Handler Pattern (server.py, `execute_tool()`)
Each tool follows the same pattern:
```python
elif tool_name == "check_health":
    results = {}
    results["whatsapp"] = "connected" if wa.status_sync().get("connected") else "disconnected"
    results["gmail"] = "authenticated" if db.query(IntegrationConfig)... else "not configured"
    results["tavily"] = "configured" if resolve_api_key("tavily", tenant_id) else "missing"
    results["sidecar"] = "online" if requests.get("http://localhost:8767/health").status_code == 200 else "offline"
    summary = "\\n".join(f"  {k}: {'✅' if v == 'connected' or v == 'online' or v == 'authenticated' or v == 'configured' else '❌' + ' ' + v}" for k, v in results.items())
    return f"**System Health**\\n{summary}"
```

## Registration Checklist
For each new tool:
1. **Tool schema**: Add numbered entry in `AGENT_TOOL_SCHEMA` string (server.py ~line 4380)
2. **Handler**: Add `elif tool_name == "check_health":` in `execute_tool()` (server.py ~line 3320)
3. **Read-only list**: Add to the "Read-only tools" paragraph in system prompt if read-only
4. **data_modifying_tools**: Add to `data_modifying_tools` set if data-modifying
5. **VOICE_WRITE_TOOLS**: If data-modifying, add to `VOICE_WRITE_TOOLS` list (line ~6380) for staging
6. **_build_pending_description**: If added to `VOICE_WRITE_TOOLS`, add an `elif name == "..."` case
   in `_build_pending_description` (line ~6901) with a human-readable confirmation prompt.
   Without this, the tool hits the generic fallback which relies on `_BUILD_DESC_FALLBACK_COUNT`
   being initialized. See `references/confirmation-flow-architecture-june29.md` Section 7 for details.
7. **Examples**: Add usage example in the examples section
8. **Restart server**: Python imports cadence_template.py at module level — restart required
