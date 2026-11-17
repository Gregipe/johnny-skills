# Two-Pass Classification — REVERTED (Jun 17, 2026)

> **Status:** This approach was implemented, tested, and reverted. It did not solve the problem. The root cause was thread contamination, not pipeline-data-induced classification failure.

## Why It Failed

The two-pass architecture was built on the assumption that pipeline data was causing misclassification. Testing with a fresh thread revealed this assumption was wrong: the original single-pass prompt works correctly when thread history is clean.

**Failures:**
1. `thread_type` was undefined in Pass 1 scope (line 6801), causing silent crashes that fell through to full Pass 2
2. The regex-based intent parsing (`r"^COMMAND"`) was fragile — LLM didn't consistently use the preamble
3. The "minimal" Pass 1 prompt still produced capability dumps because the word "CRM" in identity triggered training-data patterns
4. Even after fixing bugs, the Prompty was over-engineered — the simple single-pass prompt worked fine with a clean thread

## What Actually Fixed the Problem

1. **Reverted AGENT_SYSTEM_PROMPT_BASE** to the original simple "How to respond" section (no CLASSIFY INTENT FIRST, no categories)
2. **Archived contaminated thread** `80123f1c` → `thread_type='archived'`
3. **Created fresh coaching thread** with zero history

## Key Learning

**Thread contamination is the primary contamination vector, not pipeline injection.** When a thread has capability-dump responses in its history, future responses follow the pattern regardless of the system prompt. The fix is thread hygiene, not architectural changes to the LLM call flow.

## What Survived

The `_guard_single_action` and `_split_partial_rejection` functions added during this session remain in `server.py` and are still active.

## If Revisiting

If two-pass is attempted again:
1. Extract `thread_type` BEFORE Pass 1
2. Use a simpler intent marker (maybe structured output instead of regex)
3. Test with a clean thread first to establish baseline
4. Only proceed if the single-pass approach fails with clean history

## The Real Root Cause (Discovered After Revert)

After reverting the two-pass architecture and restoring the original simple prompt, capability dumps persisted on thread `80123f1c`. Testing with a fresh thread (zero history) proved the single-pass prompt was correct: "Hi Ava" → "Evening, Greg. How's the day treating you?"

The contamination was in the **thread history**, not the pipeline injection. 93+ messages in `80123f1c` included prior capability-dump responses. The LLM loads the last 50 as context and follows the pattern it sees — thread history overrides system prompt instructions when they conflict.

This means the original hypothesis ("pipeline data causes action bias") was wrong. The pipeline data is fine. The problem is that once a thread accumulates bad responses, they become self-reinforcing.

## Lessons

1. **Test hypothesis before building.** The two-pass architecture was 245 lines of code built on an untested assumption. A fresh-thread test at the start would have shown the prompt was correct.
2. **Thread contamination overrides system prompt.** More powerful priming than pipeline data or prompt rules.
3. **Fresh thread isolation is the definitive debugging technique** for behavioral issues. If it works on a clean thread, the code is correct.
