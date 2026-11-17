# Confirmation Flow Pitfalls Cross-Reference

The `ara-agent-tools` skill governs the tool dispatcher that executes `create_action` and other data-modifying tools. The confirmation flow (voice note → proposal → confirm → execute) is where most tool execution bugs surface.

**Primary reference**: `ara-agent-chat-debugging` → `references/confirmation-flow-pitfalls.md`

That document covers 32+ pitfalls including:
- Date strings in DateTime columns → TypeError (fixed: parse before INSERT)
- Missing NOT NULL columns → IntegrityError (fixed: set `action_type="manual"`)  
- PENDING_TTL expiry → orphaned "yes" → LLM hallucination (fixed: 600s)
- Route collisions blocking action GET (fixed: rename lead endpoint)
- Backup restores wiping prior fixes (prevention: commit after each fix)
- WhatsApp sidecar dedup never persisted (fixed: `saveDedup()` inside function)
- `_build_pending_description` missing tool cases → raw tool names (fixed: added cases)
- `_BUILD_DESC_FALLBACK_COUNT` never initialized → 500 on /api/voice/stage (July 2026: add init + explicit case for update_action)

The `tool-handler-safety-rules.md` in this skill covers the code-level fixes.
