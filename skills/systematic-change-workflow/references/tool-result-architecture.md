# ToolResult Architecture — ARA Execution Response Layer

## Context

Built June 2026 to replace the fragile two-LLM-call follow-up pipeline. The old approach: execute tools → call LLM again to rephrase results (wasted tokens, 1-3s latency). 

Current architecture: tools return native `ToolResult` dataclass → pure Python `render_results()` builds user-facing string → structured JSON persisted to DB and returned in API response.

## Core Files

| File | Purpose |
|------|---------|
| `/opt/ara/tool_results.py` | `ToolResult`, `Suggestion`, `ToolError` dataclasses; error taxonomy with params; verb map; dependency map; `from_legacy_string` adapter |
| `/opt/ara/render_results.py` | `render_results(results, channel)` — pure function, no LLM calls |
| `/opt/ara/server.py` (lines ~5139-5157) | Execute loop → in-loop dependency check → `render_results` → persist to DB |

## Architecture

```
LLM generates [TOOL_CALL: create_lead] + [ACTION: NOW]
  → execute_tool() returns ToolResult (native)
  → in-loop dependency check: skip if dependency failed for same entity
  → render_results() builds user-facing string
  → stored in AgentChatMessage.tool_results (JSON via to_dict)
  → returned in API response as tool_results array
  → injected into history as [TOOL_RESULTS: ...] on next turn
```

## The ToolResult Contract

```python
@dataclass
class ToolResult:
    ok: bool                     # success/failure
    tool: str                    # "create_lead"
    verb: str                    # "Created lead" (from TOOL_VERB_MAP or override)
    entity: str                  # "Jimmie Tete"
    entity_id: str               # DB ID (used for dependency matching)
    summary: str                 # One line WITHOUT entity name or emoji
    details: dict                # Structured fields
    suggestions: list[Suggestion]# Action-requiring follow-ups
    error: Optional[ToolError]   # Structured error with code + params + recovery
```

## ToolError with Params

```python
@dataclass
class ToolError:
    code: str                    # From ERROR_CODES
    message: str                 # Human-readable, specific to the call
    recovery: str = ""           # What the user can do
    retryable: bool = False
    params: dict = {}            # Template fill-ins: {"hint": ..., "existing": ...}
```

Templates use `str.format(**err.params)` not blind `.replace()`. Example:
- Template: `"I couldn't find anyone matching '{hint}'. Want me to create them?"`
- Params: `{"hint": "Raj"}`
- Output: `"I couldn't find anyone matching 'Raj'. Want me to create them?"`

## Error Taxonomy

| Code | Params | Recovery |
|------|--------|----------|
| `LEAD_NOT_FOUND` | `{"hint": name}` | "I couldn't find anyone matching {hint}. Want me to create them?" |
| `AMBIGUOUS_LEAD` | — | "I found several matches: {detail}. Which one did you mean?" |
| `DUPLICATE_PHONE` | `{"existing": name}` | "That phone is already on file for {existing}. Update them instead?" |
| `MISSING_ARG` | `{"field": arg}` | "I need {field} to do that — can you share it?" |
| `CONTACT_UNREACHABLE` | `{"entity": name}` | "{entity} has no phone number on file. Add one?" |
| `INVALID_VALUE` | `{"field": val, "allowed": vals}` | "{field} must be one of {allowed}." |
| `SIDECAR_DOWN` | — | "WhatsApp disconnected. Will queue." |
| `SKIPPED_DEPENDENCY` | `{"failed_tool": name}` | Always self-explained |
| `UNKNOWN` | — | Falls to template fallback |

## Dependency Map (`DEPENDS_MAP`)

Checked **before** each `execute_tool()` call — prevents dependent tools from running when a dependency failed:

```python
DEPENDS_MAP = {
    "send_whatsapp":     {"create_lead", "update_lead"},
    "create_deal":       {"create_lead"},
    "trigger_cadence":   {"create_lead"},
    "schedule_message":  {"create_lead", "update_lead"},
    "schedule_email":    {"create_lead", "update_lead"},
    "send_email":        {"create_lead", "update_lead"},
    "attach_to_deal":    {"create_lead"},
}
```

Entity matching via `_same_entity()`: compares `entity_id` first, falls back to exact (case-folded) name match. **Never post-hoc rewrite** — results are final after `execute_tool()` returns.

## from_legacy_string Adapter

Converts old-format strings to ToolResult. Handles these prefixes in order:

| Prefix | Routes to |
|--------|-----------|
| `⚠️` / `⚠` | `UNKNOWN` (never success) |
| `Error:` / `Error ` | `UNKNOWN` |
| `Tool 'x': Error:` / `: Error` | `UNKNOWN` |
| `AmbiguousLeadError:` / `AmbiguousLead:` | `AMBIGUOUS_LEAD` with candidate detail |
| `LeadNotFound:` | `LEAD_NOT_FOUND` with params={"hint": ...} |
| `✅ Name: text` | Success (entity=Name, summary=text) |
| Anything else | `UNKNOWN` |

## Renderer Output Format

| Scenario | Output |
|----------|--------|
| Single success | `✅ Created lead Jimmie Tete: phone 0123456789, company Bajaj` |
| Multi-tool same entity | `✅ Jimmie Tete — done: • Created lead: ... • Messaged: ...` |
| Partial failure | `Done 2 of 3: ✅ Created lead: ... ❌ send_whatsapp: Contact not found. Add one?` |
| All failure | `❌ {error.recovery}` |
| WhatsApp channel | Bullets → `- `, capped at 900 chars (truncate summaries, keep errors/recovery) |
| Suggestions | `↪ Would you like me to create a deal?` |

## API Response

Agent chat endpoint returns both rendered text and structured data:

```json
{
  "response": "✅ Created lead Jimmie Tete: phone ...",
  "thread_id": "abc123",
  "tool_results": [{"ok": true, "tool": "create_lead", "entity": "Jimmie Tete", ...}]
}
```

## Migration Status (June 2026)

**All ~33 tools return native ToolResult.** `from_legacy_string` is only used for:
- Residual read-only tools (get_pipeline_summary, search_knowledge_base, etc.)
- Exception returns that weren't migrated (ValueError, generic Exception catches in execute_tool)

## Test Suite

`tests/test_render_results.py` (23 tests):
- Single/multi/partial/all-failure formatting
- from_legacy_string all 6 adapter paths
- Suggestion rendering + dedup + cap
- WhatsApp 900-char cap
- Error params template rendering
- Round-trip: to_dict → JSON → reconstruct

## History

- Pre-build: 2-LLM-call follow-up pipeline (expensive, fragile)
- June 12 Ship 1: ToolResult + render_results created, response block swapped
- June 12 Ship 2: 6 priority tools migrated to native ToolResult
- June 12 Ship 3: All remaining 20 tools migrated
- June 12 Review: 10 bugs found (R-1 through R-10)
- June 12 Phase 1-5: All 10 bugs fixed, 23 tests added, 253 total
