# ToolResult Architecture — ARA Build Spec (June 2026)

Design for replacing string-based tool execution results with structured `ToolResult` objects and a pure-function renderer.

Source: External code advisor recommendation (June 12, 2026). Adopted as Option B: structured results at the source + narrow Option C (conditional LLM micro-call for unclassified errors only).

## Motivation

The old two-LLM-call architecture (execute tools → feed raw results into a 2nd LLM call to rephrase naturally) was wasteful (~$0.02-0.05 per action, 1-3s latency). The replacement single-call template-based response was too basic — raw tool output, generic error messages, no SUGGEST_DEAL follow-up, no fallback.

**The root problem:** Tools return prose strings. The response builder has to parse strings to extract structured data. If tools returned structured objects instead, the parsing layer disappears.

## Core Pattern

Tool returns ToolResult object (not string) → execute_tool() collects list[ToolResult] → render_results() produces user-facing string (pure function, no LLM). Render uses composition rules + error taxonomy templates.

### ToolResult Dataclass

Fields: ok (bool), tool (str), verb (str — past tense: "Created lead"), entity (str — "Jimmie Tete"), entity_id (str), details (dict), summary (str — human fragment WITHOUT entity name, emoji, or markers), suggestions (list of Suggestion), error (ToolError or None).

Key rules: summary never contains entity name, emoji, or markers. suggestions replaces ALL inline string markers like [SUGGEST_DEAL:]. Every failure returns a coded ToolResult.fail() — no bare `return "Error: ..."`.

### Error Taxonomy

- LEAD_NOT_FOUND: "I couldn't find anyone matching '{hint}'. Want me to create them?"
- AMBIGUOUS_LEAD: "I found {n} matches: {names}. Which one?"
- DUPLICATE_PHONE: "That phone is on file for {existing}. Update them instead?"
- MISSING_ARG: "I need {field} — can you share it?"
- CONTACT_UNREACHABLE: "{entity} has no phone. Add one?"
- SIDECAR_DOWN: "WhatsApp disconnected. I'll queue and retry." (retryable)
- RATE_LIMITED: "Rate-limited — say 'retry' in a minute." (retryable)
- NOT_CONFIGURED: "{what} isn't set up yet — go to Settings."
- UNKNOWN: Triggers the conditional micro-LLM call (Part 3)

~90% of real errors have recovery templates.

### Renderer Composition Rules

One pure function: render_results(results, channel="dashboard") -> str

1. Single success: ✅ {verb} {entity}{": " + summary if summary}
2. Multi-tool, same entity: Bullet list under header ✅ {entity} — done:
3. Multi-entity: One bullet group per entity
4. Partial failure: Leads with ❌, includes recovery of first failure
5. All failure: ❌ {error.message}\n{error.recovery}
6. Suggestions: Deduped by kind+args, capped at 2, prefixed ↪
7. WhatsApp: Replace • with -, cap at 900 chars (truncate summaries first)

### Dependency Map

If one tool fails, skip later tools that depend on it referencing the same entity. Maps: send_whatsapp depends on create_lead/update_lead; create_deal depends on create_lead; trigger_cadence depends on create_lead.

### Conditional Micro-call (Part 3)

Only fires when any result has error.code == "UNKNOWN" (~10% of errors). Model: cheapest, max_tokens 150, timeout 8s, NO retry. On exception: return None → renderer falls back to template rule 5.

### Legacy Adapter

Until all ~25 tools are migrated, from_legacy_string(tool, raw) -> ToolResult handles:
- "Error: ..." → ToolResult.fail(tool, "UNKNOWN", ...)
- "✅ Name: details [SUGGEST_DEAL: ...]" → ToolResult.success(...) with extracted suggestion

## Build Order

1. Part 0 (persist results to DB) + Part 4.1 (resolve_lead AmbiguousLeadError) — ship first
2. Part 1 (ToolResult dataclass) + legacy adapter + swap response block to render_results
3. Part 2 (renderer) — add composition rules
4. Migrate 6 priority tools (create_lead, update_lead, send_whatsapp, create_deal, update_deal_stage, search_leads)
5. Part 3 (micro-call) — last, enhancement

## Changes Made So Far (June 12, 2026)

Part 0 started: Added tool_results column to AgentChatMessage + migration. Added AmbiguousLeadError. Updated resolve_lead. Updated execute_tool catch block.
