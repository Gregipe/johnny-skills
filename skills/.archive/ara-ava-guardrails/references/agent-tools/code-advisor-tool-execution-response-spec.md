# Code Advisor Spec — Tool Execution Response Layer Design

Source: Internal code advisor commissioned by Greg June 2026.

## Decision

**Option B, implemented at the source** (structured `ToolResult` objects, not string parsing)
+ a narrow slice of Option C (one cheap conditional LLM call for unclassified errors).
Reject A and D. See session June 12, 2026 for full rationale.

## Key Constraints

- Voice notes already 3-5s latency. Every 100ms counts.
- Build what the spec says — don't over-engineer.
- `from_legacy_string` is the adapter bridge. Never add new tools returning old-format strings.

## Architecture

1. **ToolResult dataclass** — Every tool returns structured data, not prose strings. The renderer owns presentation.
2. **Error taxonomy with recovery templates** — ~90% of errors get specific, helpful recovery text with zero LLM calls.
3. **DEPENDS_MAP** — If tool A fails, dependent tools targeting the same entity auto-skip.
4. **Channel-aware renderer** — WhatsApp gets `- ` bullets and 900-char cap; dashboard gets `• ` bullets.
5. **Conditional micro-call** (Part 3) — One cheap LLM call for UNKNOWN errors only. Not built yet.
6. **API response** returns `tool_results` JSON array alongside the rendered `response` text.
7. **Voice notes** — ALL data-modifying voice actions require confirmation (STT garbles).

## Anti-patterns

- **2nd LLM call for synthesis** — The single-call architecture is intentional.
- **String concatenation rendering** — Always go through ToolResult -> render_results().
- **Silent dependency failures** — Always apply dependency skips; show SKIPPED_DEPENDENCY.

## Migration Order

create_lead → update_lead → send_whatsapp → create_deal → update_deal_stage → search_leads
Then mutation tools: attach_to_deal, update_deal, send_whatsapp_instantly, etc.
Read-only tools (get_*, search_*) can stay in the adapter indefinitely.
