# One-Question-At-A-Time Fix (June 2026)

Session-specific detail for the three-layer fix that made ARA's induction
flow ask one question per response instead of dumping 5-7 questions.

## Symptom

Greg reported the induction was "more like a dump" — Ava asked 5-7 questions
per response instead of one at a time. The system prompt already contained
"Ask ONE question at a time" as rule #1, but the LLM ignored it.

## Root Cause Analysis (3 Layers)

### Layer 1: System Prompt Structure

`induction_engine.py` → `INDUCTION_SYSTEM_PROMPT`

The "one question at a time" rule was buried as rule #1 under "Interaction
Rules," competing with 6 other "CRITICAL" rules. Module descriptions used
bullet lists (`- What does the company do?`, `- Who are their target
segments?`) which the LLM read as "ask all of these."

**Fix:**
- Moved "ONE QUESTION AT A TIME" to be `## THE #1 RULE` at the very top,
  before all other rules, marked NON-NEGOTIABLE
- Added explicit WRONG vs RIGHT example with multi-question vs single-question
- Rewrote every module as a numbered question queue (1, 2, 3...) instead of
  bullet lists
- Added: "Your response must contain exactly ONE question mark"

### Layer 2: Dynamic Runtime Instructions

`server.py` → `induction_chat()` endpoint, ~line 3240

The `module_instruction` strings injected into the system prompt literally
said "Ask for admin name, email, and WhatsApp number" — instructing 3
questions at once. Even with a perfect system prompt, the LLM followed
this dynamic instruction.

**Fix (2 strings patched):**

String 1 (substantial KB path):
```python
# BEFORE:
"Ask for admin name, email, and WhatsApp number concisely."
# AFTER:
"Start by asking ONLY for the admin's name. Do NOT ask for email and WhatsApp
in the same response — you will ask for those in subsequent turns. ONE
question at a time."
```

String 2 (fresh start path):
```python
# BEFORE:
"Begin by asking for the admin's name, email, and WhatsApp number."
# AFTER:
"CRITICAL: Ask ONE question at a time. Begin by asking ONLY for the admin's
name. Do NOT ask for email or WhatsApp number in the same response — you
will ask for those one at a time in subsequent turns."
```

### Layer 3: Conversation History Mimicry

`induction_engine.py` → `INDUCTION_SYSTEM_PROMPT` (history override)

Old multi-question assistant responses stored in `CoachingLog` were replayed
into the LLM context as conversation history. The LLM treated these as
few-shot examples and mimicked the multi-question pattern, overriding even
the strengthened system prompt.

**Fix:** Added to the system prompt, immediately after the #1 RULE section:
```
IMPORTANT: If older conversation history in this chat contains responses
where multiple questions were asked, IGNORE that pattern. Those were
generated under an old system. From this point forward, you ask ONE question
per response — no exceptions.
```

## Verification

1. Deployed both file changes to production server
2. Restarted `ara-server` systemd service
3. Smoke-tested with Greg's tenant (3e736242) — 280 skills, extensive
   old history with multi-question responses
4. LLM responded with exactly ONE question at the end, confirming Layer 3
   override works even against strong history precedent

## Files Modified

- `/opt/ara/induction_engine.py` — Full rewrite of `INDUCTION_SYSTEM_PROMPT`
- `/opt/ara/server.py` — 2 `module_instruction` strings patched (lines ~3247, ~3249)

## Key Lesson

When an LLM ignores a system prompt instruction, check ALL three layers:
1. Is the instruction prominent enough in the system prompt? (Layer 1)
2. Is dynamic runtime code overriding it with a contradictory instruction? (Layer 2)
3. Is conversation history teaching the LLM to ignore it? (Layer 3)

Fixing only one layer is insufficient. Layer 3 (history mimicry) is the
most commonly missed because it's invisible — the old responses look
harmless in context but act as few-shot examples.
