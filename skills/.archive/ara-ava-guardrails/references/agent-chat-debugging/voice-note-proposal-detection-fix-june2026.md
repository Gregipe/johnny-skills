# Fix: Voice-Note Proposal Detection & Pending Description Fallback

**Applied:** June 15, 2026 (commit `801c140`)

## Problem

Voice-note proposals like "Shall I set a reminder? Sound right?" generated WITHOUT `[TOOL_CALL:]` blocks caused `is_data_modifying=False`, so no `ActionItem` was created. When the user replied, `_live_pending_for_tenant` found nothing and the message routed as a fresh request. The LLM pattern-matched to polluted conversation history.

## Fix 1: Expanded `_claims_action_without_call`

Location: `server.py` ~line 5256

The function now catches three categories:
1. **Past-tense claims** (existing): "I've updated...", "Sent the message"
2. **Future/proposal language** (NEW): "Shall I set...", "I'll create...", "Can I add..."
3. **Confirmation questions** (NEW): "Sound right?", "That work?"

```python
_action_verbs = (
    r"set|send|create|add|update|schedule|remind|message|email|text|"
    r"start|run|trigger|fire|execute|save|log|escalate|"
    r"cancel|delete|remove|import|attach|detach|move|qualify"
)
claim_pats = [
    # 1. Past-tense claims (existing)
    _cre.compile(r"(?i)(?:i['']v[em]|i have|has been|updated|corrected|changed|"
                 r"set\s+(?:the|her|his|their|your)?\s*(?:email|phone|name))"),
    _cre.compile(r"(?i)(?:sent|messaged|texted|emailed|called|contacted)\s+"
                 r"(?:the|her|him|them|that|this)"),
    # 2. Future/proposal language — excludes "what can/should I" to avoid
    #    false positives on capability questions
    _cre.compile(r"(?i)(?<!what\s)(?:shall\s+i|want\s+me\s+to|should\s+i|can\s+i|"
                 r"let\s+me|i['']ll|i\s+will|i\s+can)\s+(?:" + _action_verbs + r")"),
    # 3. Proposal confirmation questions
    _cre.compile(r"(?i)(?:sound\s+(?:right|good|ok|alright)|that\s+(?:right|ok|work|sound))\?"),
]
```

### False positive guards

- `(?<!what\s)` negative lookbehind excludes "what can I do", "what should I set"
- Generic verbs excluded: `do`, `make`, `call` — too many innocuous phrases ("What can I do?", "I'll make a note", "Let me call you")
- Read-only verbs excluded: `look`, `check`, `search`, `find` — "Shall I look up..." doesn't trigger

### How it works

When triggered, the existing observe-loop nudge fires:
```
"You described an action but issued no tool call, so nothing changed.
Either emit the correct tool call now, or tell the user plainly that
you cannot do it."
```

The LLM gets a second chance to add `[TOOL_CALL:]` blocks with full conversation context.

## Fix 2: `_build_pending_description`

Location: `server.py` ~line 5196

When `resp_clean` is empty after stripping `[ACTION: ASK]` and `[TOOL_CALL:]` markers, builds a human-readable description from tool call args:

```python
def _build_pending_description(tool_calls):
    parts = []
    for tc in tool_calls:
        name = tc.get("name", "") or tc.get("tool", "")
        args = tc.get("args", {}) or {}
        if name == "set_reminder":
            parts.append(f"Set reminder: {args.get('title', '') or args.get('message', '')}")
        elif name == "set_cron":
            freq = args.get("frequency", "")
            t = args.get("time", "")
            suffix = f" ({freq} at {t})" if freq and t else ""
            parts.append(f"Schedule: {args.get('title', '')}{suffix}")
        elif name == "create_lead":
            ...
        # ... one branch per tool type, plus generic fallback
    return "; ".join(parts) if parts else "Pending confirmation"
```

This ensures `_classify_confirmation` always has context — never called with an empty proposal.

## Fix 3: `[TOOL_CALL:]` stripping from `resp_clean`

Added at the ask-gate (line ~5095): strip `[TOOL_CALL: ...]` markers from `resp_clean` BEFORE checking emptiness. Pattern: `_re.sub(r'\s*\[TOOL_CALL:\s*[^\]]*\]', '', resp_clean)`. This prevents raw JSON from leaking into the ActionItem description and the classifier prompt.

## Verification

- **54 new tests** added to `test_pending_confirmation.py`: proposal detection (16 tests), description builder (13 tests), integration (2 tests), false positive guards (6 tests)
- **Live classifier verified** with production API key: "Set reminder: Send pricing to Rajesh Sharma..." + "Yes set it in" → `confirm`
- **Unrelated path verified**: same proposal + "set Rajesh to qualified" → `unrelated`
- **Full suite**: 330 passed, 2 skipped, mypy clean

## Follow-Up Fixes (Same Day — Jun 15, 2026)

### Fix 4: Voice handler reads `db_response`, not `response` (commit `7c79804`)

The voice handler at `whatsapp_voice_inbound()` line 9724 was using `data_resp.get("response", "")` which omits the `[PENDING]` confirmation prompt. Fixed to use `data_resp.get("db_response", "") or data_resp.get("response", "")`. The `db_response` field includes the confirmation prompt for pending actions and equals `response` otherwise (line 5187).

### Fix 5: Structured summary in user-facing response (commit `0059075`)

When the ask-gate creates a pending ActionItem, `_build_pending_description` output is now appended to the user-facing response text. The user sees both the LLM's natural prose AND a structured summary of what will happen:

```
⏳ Confirm? Reply yes/send to proceed:
You're right — fair catch. I'll create that action.

Create action: Send pricing information to Rajesh
```

Previously only the LLM's vague prose was shown ("You're right — let me set it now"), with no indication of WHAT was being proposed.

### Fix 6: Nudge prompt rewording (commit `f7acd4d`)

The claim/no-call nudge at line 5056 was changed from:
```
"You described an action but issued no tool call, so nothing changed.
Either emit the correct tool call now, or tell the user plainly that you cannot do it."
```
To:
```
"You claimed or proposed an action but issued no tool call, so nothing happened.
Add the correct [TOOL_CALL:] block, and phrase your response as a proposal the user
needs to confirm — use 'I'll...' or 'Shall I...' language, NOT 'let me X now' or
'Done'. The tool call will NOT execute yet; the user must approve it first.
Or tell the user plainly that you cannot do it."
```

The word "now" in the old prompt primed the LLM to say "Let me create that action NOW" — which reads like completion, not pending. Explicitly forbidding "let me X now" and "Done" phrases prevents misleading user-facing text.

### Fix 7: `[PENDING]` prefix replaced with clearer format

Changed from `[PENDING - Reply 'send it' or 'confirm' to proceed]` to `⏳ Confirm? Reply yes/send to proceed:`. The emoji signals "waiting" not "done", and the simpler language is easier to scan on mobile.

### Fix 8: Context window 20 → 50 (commit `6156890`)

Line 5499: `.limit(20)` → `.limit(50)`. Covers topic-switching within a session. DeepSeek V4 has 128K token window — ample headroom.

### Fix 9: Conversation history poisoning purge

5 hallucinated assistant messages from Jun 14-15 deleted from the coaching thread (tenant `3e736242`). These were "set it in → Arun Matthew?" loops that taught the LLM to associate ambiguous queries with the wrong lead. Each failed confirmation reinforced the signal. Purging dropped "Arun Matthew" mentions from 18 → 13 (remaining 13 are legitimate).

### Fix 10: `_build_recent_actions_block` — live fact sheet (commit `ed39e0e`)

New function injected into the system prompt at line 5585. Queries ActionItem per-tenant, ordered by `coalesce(resolved_at, created_at) desc`, limit 7. Renders one line per action with human status phrases: `⏳ awaiting your OK` / `✅ done` / `✅ sent · awaiting reply` / `✖️ cancelled` / `⚠️ failed`. No caching — state read live from DB every call.

The model resolves "it"/"that" from conversation history against this block. No re-ranking, no lead-scoping. Heading includes instruction: "If unclear which one, ask — don't guess."

This enables queries like "did you do it?", "did that send?", "what happened to the Rajesh pricing reminder?" to return live state from the fact sheet without tool calls.

## Related

- `ara-agent-chat-debugging` SKILL.md: "Bug: LLM Never Generated a Tool Call — Variant 3"
- `ara-agent-chat-debugging` Pitfall #15: empty descriptions in pending ActionItems
