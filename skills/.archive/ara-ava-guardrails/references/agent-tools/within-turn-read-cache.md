# Within-Turn Read Cache (July 2026)

When the observe loop is several steps deep, the LLM re-fetches data it already retrieved because prior tool results scroll out of its attention window. This causes duplicate read-only calls (same `get_action_items`, same `query_database`) that waste steps and push context further.

## Implementation

In `_run_observe_loop()` in `/opt/ara/server.py`:

```python
# At start of loop
_read_cache = {}

# Wrapper
def _cached_execute(tn, args, db, wa, tenant_id, _read_cache):
    if get_tool_read_only(tn):
        key = f"{tn}:{json.dumps(args, sort_keys=True)}"
        if key in _read_cache:
            return _read_cache[key]  # cached hit
        result = execute_tool(tn, args, db, wa, tenant_id)
        _read_cache[key] = result
        return result
    return execute_tool(tn, args, db, wa, tenant_id)  # writes bypass
```

All read-tool execution calls in the observe loop route through `_cached_execute` instead of `execute_tool` directly.

## Safety Constraints

- **Within-turn only** — cache cleared between turns (`_read_cache = {}` at loop start)
- **Read-only tools only** — writes bypass the cache unconditionally. Never cache writes — data can change between calls within the same turn (e.g., a create_lead followed by a send_whatsapp to that lead).
- **Exact args match** — `json.dumps(args, sort_keys=True)`. Even minor arg differences (e.g., different due_at) produce different cache keys.
- **NOT a text-injection guard** — this prevents literal redundant work by recognizing identical tool calls. It does not infer intent from prose.

## Results

"update Amardeep deadline to Friday + WhatsApp him":
- Before: 6 tools (duplicate get_action_items ×2, duplicate query_database ×2, spurious search_memory, no send_whatsapp called)
- After: 5 tools (0 duplicates, 0 spurious calls, send_whatsapp actually executed)

## See Also

Full context in [ara-ava-guardrails: context-discipline-june2026.md](../ara-ava-guardrails/references/context-discipline-june2026.md) — Case Study 7.
