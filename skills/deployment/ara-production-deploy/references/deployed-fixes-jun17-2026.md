# Deployed Fixes — June 17, 2026

Three code-level defenses deployed to ARA production (`/opt/ara/server.py`) alongside a system prompt redesign.

## Fix 1: Single-Action Guard (`_guard_single_action`)

**Problem:** LLM bundled unsolicited tools into proposals. "Send WhatsApp to Jimmie" became "create Shriram deal + send WhatsApp."

**Solution:** After LLM generates tool calls, scan user message for action verbs (send, create, update, set, schedule, etc.). If exactly ONE verb found but LLM proposed MULTIPLE data-modifying tools, auto-trim to matching tool only.

**Location in server.py:** After `_build_pending_description()`, before `_AIStore` creation.

**Pitfall:** Multi-action requests ("create a deal AND send a WhatsApp") have two verbs → guard doesn't fire. This is correct behavior.

## Fix 2: Partial Confirmation (`_split_partial_rejection`)

**Problem:** "Ignore Shriram, just do WhatsApp" cancelled EVERYTHING because the confirmation classifier returned all-or-nothing "reject."

**Solution:** In the reject handler, parse user message for "ignore X" / "skip X" / "just Y" patterns, match entity names against pending tool call args, split into keep vs reject lists. Execute kept tools, drop rejected ones.

**Location in server.py:** Inside the `elif _verdict == "reject":` handler, before full cancellation.

**Pitfall:** For genuinely ambiguous entity names, partial rejection may not match (falls through to normal full reject — safe default).

## Fix 3: search_conversation_history ToolResult.fail() Bug

**Problem:** `ToolResult.fail()` called with 2 args `(tool, message)` but requires 3 `(tool, code, message)`. When Ava tried `search_conversation_history`, the error itself crashed with `missing 1 required positional argument: 'message'`.

**Solution:** Added `"MISSING_ARG"` and `"SEARCH_FAILED"` error codes to the two `ToolResult.fail()` calls in the search_conversation_history handler (lines 5224 and 5243).

## Fix 4: System Prompt Redesign — CLASSIFY INTENT FIRST

**Problem:** Classification rules scattered across 7 prompt sections. Pipeline data overwhelmed them. LLM defaulted to pipeline-action mode for ambiguous inputs.

**Solution:** Replaced "How to respond" + "Reasoning Preamble" + "Answering Simple Questions" + "Anti-Patterns" sections with a single unified framework:
- 5 intent types: QUESTION / COMMAND / HYPOTHETICAL / CONVERSATION / AMBIGUOUS
- "Use your reasoning, not keyword matching"
- Reasoning Preamble: "Got it — [TYPE]. Greg wants [X]. I'll [plan]."
- Old Rule #6 (ACTION/STRATEGIC/etc.) updated to match new framework

**Deployment note:** This is a prompt-only fix — no code behavior change. Can be reverted by restoring AGENT_SYSTEM_PROMPT_BASE.

## Conversation History Cleanup (Same Session)

During the same session, the coaching thread (80123f1c) was surgically cleaned:
- 21 contaminated messages deleted (Shriram/Ajay references)
- 5 orphaned user messages deleted
- 3 hallucinated assistant proposals deleted
- 5 stale pending actions cancelled (all proposing Ajay Fageria/Shriram Finance)

**Cleanup methodology:** See `ara-agent-chat-debugging/references/contamination-cycle.md` for the self-reinforcing cycle pattern and full cleanup protocol.

## Backups

All server.py backups:
- `/opt/ara/server.py.bak-20260617-guard` — before single-action guard + partial confirmation
- `/opt/ara/server.py.bak-20260617-hypo` — before hypothetical question guard (REVERTED)
- `/opt/ara/server.py.bak-20260617-classify-v2` — before CLASSIFY INTENT FIRST deployment
