# Enforcer Question Detection Pattern (June 2026)

## Problem

The pre-execution enforcer fires on data-modifying keywords (update, set, create, send, cron, etc.). But "Can you set cron jobs?" is a **question about capability**, not an instruction to execute. The enforcer's `_has_intent` check matches on `"set"` and `"cron"`, triggering a 30-50 second enforcer re-call loop that wastes tokens and creates dead air.

## The Fix (3-Layer Detection)

Skip the enforcer when the user's message is clearly a question. Three layers of detection:

1. **Question mark check** — `"?" in _msg_lower` catches most standard questions.
2. **Start-with check** — `_msg_clean.startswith(_question_words)` catches question-lead sentences.
3. **Substring check** — `any(" " + w + " " in " " + _msg_clean[:60] + " " for w in _question_words)` catches questions embedded after names/greetings like `"🎤 hey eva, could you..."` or `"Hey Greg - can you set..."`.

**Voice note emoji stripping:** Voice transcripts arrive prefixed with `🎤`. The `_msg_clean` must strip these before the startswith check, otherwise `"🎤 hey eva, could you..."` starts with `🎤`, not `"could"`.

```python
# Strip common emoji/prefix noise like 🎤 (voice note), then check for question patterns
_msg_clean = _msg_lower.strip().lstrip("\U0001f3a4\U0001f44d\U0001f4ac\U0001f4ad\ufe0f\u2728\U0001f31f").strip()
_question_words = ("can", "could", "would", "do", "does", "is", "are", "will", "what", "how", "should", "may")
_is_question = "?" in _msg_lower or _msg_clean.startswith(_question_words) or any(
    " " + w + " " in " " + _msg_clean[:60] + " " for w in _question_words
)
if _has_intent and not _has_tool and not _is_question:
    # ... enforcer logic (skipped for questions)
```

## Key Insight

The question pattern `"can you X?"` conflates two LLM failure modes:
- **Genuine hallucination** (LLM says "updated" without a tool call) — rare, occurs when LLM confuses describing with doing
- **Question about capability** (LLM answers "Yes I can" naturally) — common, should never trigger the enforcer

The `_is_question` check cleanly separates these. Questions about capability should be answered naturally — the metacognition layer (`log_capability_request`) handles cases where Ava genuinely can't do what's being asked.

## Pitfalls

- **Don't over-broaden the question list** — `"what did you do to my lead?"` is also a question but shouldn't skip the enforcer if the enforcer would catch a phantom update claim. The current startswith list (can/could/would/do/does/is/are/will/what/how) is safe because the data-modifying keywords (set, create, update, etc.) only trigger when the user is ASKING for a change, not asking ABOUT it.
- **The "?" check** catches ALL punctuated questions, including "You can set cron jobs?" — which IS a question about capability. The startswith catches questions without "?" (e.g., "Can you set cron jobs" without punctuation).
- The substring check is essential for voice notes — Without it, "🎤 hey eva, could you set a reminder" starts with "hey" not "could", and the enforcer fires. The substring " could " in the first 60 chars catches this. Ref: ara-voice-pipeline references/voice-interim-question-detection-june2026.md.
- Chinese/Indian/other-languages question detection — The startswith+substring approach is English-heavy. If Greg writes in Hinglish ("kya tum cron set kar sakte ho?"), the "?" check catches it. If the LLM is switched to a non-English prompt, add the local question words to `_question_words`.
- **This runs BEFORE tool call parsing** — The enforcer is positioned between the first LLM call and tool parsing. The `_is_question` check is pure string matching on the user message — no LLM call, no tokens consumed.
