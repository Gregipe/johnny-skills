# Voice Confirmation Audit Design — Phase 2 Guardrails

**Audit date:** 2026-07-04
**What:** Design review of voice write-tool confirmation flow
**Status:** Implemented

## Critical Bug Found

**`voice_confirm` was dead code.** The handler `_make_voice_confirm_handler()` existed in `voice_tools.py` but was never registered as a `FunctionSchema` in `build_voice_tools()`. The LLM was instructed to "call the voice_confirm tool" but had no such tool available. Voice writes would stage but could never execute via voice confirmation.

**Root cause:** `build_voice_tools()` iterates only over CRM tools from `/api/voice/tools`. The `voice_confirm` meta-tool (not a CRM tool) was never appended to the schemas list.

**Fix:** After the CRM-tool loop in `build_voice_tools()`, explicitly append:
```python
schemas.append(FunctionSchema(
    name="voice_confirm",
    ...
    handler=_make_voice_confirm_handler(secret, tenant_id),
))
```

## Prescribed Guardrails

### 1. Explicit confirmation keyword only
Accept only the word **"confirm"** (or "confirmed") as the affirmative. Reject "yes", "okay", "sure", "go ahead", "do it", "uh-huh", "yeah".

Rationale:
- "confirm" is 2 syllables, phonetically distinct from "cancel"
- "yes" and "no" are short, high-confusion STT words
- "okay" and "sure" are common in casual speech and easily hallucinated from noise
- "no" ↔ "go" is a classic STT confusion pair

### 2. Mandatory verbatim read-back
Before asking for confirmation, Ava MUST read the exact `description` string returned by `/api/voice/stage` — not a paraphrase. The LLM is instructed: "Read the Description back to the user VERBATIM."

### 3. pending_id required (no "latest pending" fallback)
The `voice_confirm` handler passes `pending_id` from the stage result. The server endpoint REQUIRES it — no auto-finding "most recent." This eliminates the race condition where a newly staged action B could be confirmed when the user was still discussing action A.

### 4. Risk tiering
| Tier | Tools | Confirmation |
|------|-------|-------------|
| **Tier 1** (reversible) | `update_lead_stage`, `create_lead`, `log_insight`, `save_memory`, etc. | Voice with read-back + "confirm" |
| **Tier 2** (external) | `send_whatsapp`, `send_email`, `send_whatsapp_to_owner`, etc. | Voice but read full content back |
| **Tier 3** (destructive/bulk) | `cancel_scheduled`, `detach_from_deal`, `resolve_watchlist_item`, `import_leads_from_text` | Chat-only — server enforced |

### 5. Server-side Tier 3 block
In `voice_confirm()`, after finding the pending ActionItem, scan `pending_tool_calls`. If any tool is in `VOICE_CHAT_ONLY_TOOLS`, refuse immediately with "This action type requires dashboard confirmation." This is enforced server-side, not just via prompt.

### 6. Single confirm attempt
If `voice_confirm` returns an error, do NOT retry blindly. Report and ask user to re-stage.

## System Prompt Changes

The voice system prompt was rewritten with four mandatory sections:
1. **Personality** — witty, cheerful, professional, CRM-only
2. **Topic guard** — refuse non-business queries
3. **Number pronunciation** — mobile numbers as spaced digits, dates in spoken form
4. **Confirmation flow** — 8-step protocol with explicit-keyword gate

The "yes" / "okay" / "sure" keywords are EXPLICITLY listed as NOT valid confirmations.

## Files Changed
- `voice_tools.py` — voice_confirm registered, pending_id passed, chat_only handler added
- `bot.py` — system prompt rewritten with explicit-keyword gate, read-back, Tier 3 rules
- `server.py` — VOICE_CHAT_ONLY_TOOLS, pending_id required, Tier 3 server-side block, chat_only_confirm metadata

## What Was NOT Changed
- No database.py changes — ActionItem schema already supports everything
- No dashboard_template.py changes — chat confirmation path works as-is
- Did not force chat-only — voice confirmation is the right UX with sufficient guardrails
- Did not add double confirmation ("say confirm twice") — adds friction without proportional safety gain
