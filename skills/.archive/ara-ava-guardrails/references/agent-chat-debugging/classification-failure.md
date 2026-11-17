# Classification Failures — Intent vs Keyword Matching

**Root cause pattern:** Ava's original classification used keyword matching (\"can you → CAPABILITY\", \"where → STRATEGIC\"). When a user phrased a question differently — different words, different language, different structure — the classifier failed.

## Classic Failure Case (June 2026)

**User:** \"Does the tool also allow you to create a note against the lead?\"
**Expected:** CAPABILITY_QUESTION — asking about tool features
**Actual:** Drifted to ACTION mode — tried to execute import

**Why:** \"Does...\" was not in the CAPABILITY trigger list (which had \"can you\", \"would you\", \"what happens if\"). The message fell to AMBIGUOUS and Ava guessed wrong.

## The Fix: Intent-Based Classification (v2)

Replaced keyword-matching triggers with intent reasoning:

```
Classify the user's INTENT, not their words. Do not pattern-match keywords.
Reason about what the user WANTS. Then pick the ONE category that matches.
```

**Seven categories with intent descriptions:**
- CHITCHAT — greeting or small talk
- CAPABILITY_QUESTION — asking about abilities/limits/features
- DIAGNOSTIC — investigating a problem
- ACTION — requesting execution
- STRATEGIC — asking for advice/analysis
- SIMPLE_QUESTION — asking for a specific fact
- AMBIGUOUS — genuinely unclear after reasoning

**Critical rule:** Language doesn't matter — Hindi, Hinglish, broken English, voice notes. Focus on what the user wants, not which words they used.

## How to Verify the Fix

1. Test with the exact failure case: \"Does the tool also allow...\"
2. Test in different phrasing: \"Is it possible to...\", \"Would this be supported...\"
3. Test in Hinglish: \"Kya yeh tool notes bhi support karta hai?\"
4. Ava should classify all as CAPABILITY_QUESTION and answer without calling tools

## When to Revisit

If Ava ever responds to a question about capabilities by trying to execute an action, the classification is the first thing to audit. Check `AGENT_SYSTEM_PROMPT_BASE` in server.py lines 5372-5425.
