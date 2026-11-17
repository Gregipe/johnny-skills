# Classification Over-structuring Pitfall (Jun 17, 2026)

## The Problem

Ava's intent classification was restructured from a simple "Read. Think. Respond." approach into a formal 5-category framework:

```
CLASSIFY INTENT FIRST
→ QUESTION / COMMAND / HYPOTHETICAL / CONVERSATION / AMBIGUOUS
```

This caused **every message to become a classification task** instead of a conversation. The LLM over-thought simple greetings ("Hi Ava") and defaulted to listing capabilities because the classification framework primed it to find intent even where none existed.

## The Fix

**Reverted to the original simple approach:**

```
## How to respond

Read Greg's message. Think about what he wants. 
That's your entire classification — no categories, no triggers, no checklists.

If he's greeting you, greet back warmly.
If he's asking what you can do, tell him.
If he wants you to execute, do it.
If he's not sure, ask one specific question.
```

## What Also Failed

### Two-pass classification (Pass 1 / Pass 2)
An attempt to strip pipeline data from classification by running Pass 1 (no pipeline, no tools) → classify → Pass 2 (full pipeline + tools) only for COMMANDs. This broke the greeting flow entirely because:
- Pass 1 had a separate "minimal" prompt that lost conversational context
- The regex-based routing (parsing "COMMAND" from response text) was fragile
- `thread_type` was undefined in Pass 1 scope, causing silent crashes

### Removing "CRM" from identity
The word "CRM" triggers capability-list training data patterns in LLMs. Attempted to fix by renaming Ava to "co-pilot" instead of "CRM co-pilot" — but this only addressed a symptom. The root cause was the classification framework over-structuring.

## Thread Contamination: The Deeper Root Cause

Even after reverting to the simple prompt, capability dumps persisted on thread `80123f1c`. Testing with a **fresh thread (zero history)** proved the reverted prompt was correct — "Hi Ava" → "Evening, Greg. How's the day treating you?" on a clean thread.

The thread itself was contaminated. 93+ messages in `80123f1c` included prior capability-dump responses. The LLM loads the last 50 messages as context and follows the pattern it sees — regardless of what the system prompt says. Thread history overrides system prompt instructions when they conflict.

### Debugging technique: Fresh thread isolation
When behavioral issues persist after prompt fixes, test with a brand-new thread (`thread_id` with zero messages). If the issue disappears, the thread history is contaminated. If it persists, the system prompt is the problem.

### Fix: Archive contaminated threads
When a thread's history is too deeply contaminated to surgically clean, archive it (`thread_type='archived'`) and create a fresh one. The coaching thread is auto-resolved by `thread_type='coaching'` — only one should exist.

## Key Principles

1. **Don't over-structure classification.** The LLM already knows how to respond to greetings, questions, and commands. Adding formal categories creates meta-cognition overhead that causes the LLM to over-think simple inputs. The simplest possible instruction is the most effective.

2. **Thread history is the strongest priming signal.** More powerful than the system prompt. If responses are wrong despite a correct prompt, check the thread history first. A single capability-dump response in the last 50 messages can cascade into future dumps.

3. **"CRM" in identity triggers capability-list training patterns.** LLMs trained on CRM assistant data associate "CRM" + greeting with "Here's what I can do." Removing "CRM" from identity framing can help but is a secondary fix — the primary fix is keeping the system prompt simple and the thread history clean.
