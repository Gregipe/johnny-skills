# Tool Execution Response Layer — Final Built State (June 2026)

## What Changed

**Old:** 2-LLM-call pattern — execute tools → feed raw strings into a 2nd LLM call to rephrase naturally.
**New:** Single-call pattern — execute tools → wrap in `ToolResult` objects → render via `render_results()`.

## Files

- `tool_results.py` — ToolResult, Suggestion, ToolError dataclasses; ERROR_CODES taxonomy; TOOL_VERB_MAP; DEPENDS_MAP; from_legacy_string adapter; apply_dependency_skips
- `render_results.py` — render_results() pure function
- `server.py` — execute loop wraps results, calls apply_dependency_skips + render_results

## ToolResult Dataclass

```python
@dataclass
class ToolResult:
    ok: bool
    tool: str
    verb: str = ""            # Past tense: "Created lead" (default from TOOL_VERB_MAP)
    entity: str = ""           # "Jimmie Tete"
    entity_id: str = ""        # "4a43e37a"
    details: dict = field(default_factory=dict)
    summary: str = ""          # No entity name, no emoji
    suggestions: list = field(default_factory=list)  # list[Suggestion]
    error: Optional[ToolError] = None
```

## Renderer Rules

| Scenario | Output |
|----------|--------|
| Single success | `✅ Created lead Jimmie Tete: phone ...` |
| Multi-tool, same entity | `✅ Jimmie Tete — done:\n• verb: summary\n• verb: summary` |
| Partial failure | `Done 2 of 3:\n  ✅ ...\n  ❌ tool: error.recovery` |
| All failure | `❌ error.message\nrecovery` |
| Suggestions | `↪ prompt` after body, max 2 deduped |
| WhatsApp | `- ` bullets, 900-char cap (truncates summaries, never errors) |

## Error Taxonomy (ERROR_CODES)

LEAD_NOT_FOUND, AMBIGUOUS_LEAD, DUPLICATE_PHONE, MISSING_ARG, INVALID_VALUE,
CONTACT_UNREACHABLE, SIDECAR_DOWN, RATE_LIMITED, NOT_CONFIGURED,
SKIPPED_DEPENDENCY, UNKNOWN (catch-all)

## Dependency Map

If `create_lead` fails, dependent tools targeting the same entity auto-skip:
- send_whatsapp, create_deal, trigger_cadence, schedule_message, schedule_email,
  send_email, attach_to_deal

## Migrated Tools (native ToolResult)

create_lead, update_lead, send_whatsapp, create_deal, update_deal_stage, search_leads

Remaining ~19 tools still pass through `from_legacy_string()` adapter.

## Voice Note Policy

ALL data-modifying voice actions require confirmation (STT garbles names/phones).
The voice check at `server.py:5061` overrides any `[ACTION: NOW]` marker.

## Build Order Executed

1. Part 0 — `tool_results` JSON column + migration on AgentChatMessage ✅
2. Part 4.1 — AmbiguousLeadError for resolve_lead ✅
3. Part 1 — ToolResult dataclass + legacy adapter ✅
4. Part 2 — render_results() function ✅
5. Part 5 — swap response block, import ToolResult/render_results ✅
6. Part 5 step 4 — migrate 6 priority tools ✅
7. Part 3 — micro-call for UNKNOWN errors ❌ (not built yet)
