# Intent-Based Message Classification for LLM Agents

**Why this exists:** Ava's original classification used keyword-matching ("can you", "does X", "what happens if"). When Greg asked "Does the tool also allow you to create a note against the lead?", the absence of "does X" from the trigger list caused a misclassification. Pattern-matching is fundamentally fragile — any phrasing not in the lookup table fails.

**The fix (June 17, 2026):** Replaced trigger-word matching with pure intent reasoning.

## The Prompt (Deployed)

```
## Message Classification (FIRST — before anything else)

Think about what the user WANTS. Not which words they used — what they actually want from you right now. Then pick the ONE category that matches their intent.

**How to classify:** Read the message, think about the user's goal, and choose:

- **CHITCHAT** — They're greeting you or making small talk.
  → Warm, brief response. One sentence. Stop. Never turn this into business.

- **CAPABILITY_QUESTION** — They want to know what you can or cannot do. The question is about YOUR abilities, limits, or features.
  → Answer directly. Zero tools. You know what you can do.

- **DIAGNOSTIC** — Something went wrong. They want to understand WHY.
  → Investigate with inspection tools. Cross-reference. Present evidence. Suggest fix.

- **ACTION** — They want you to EXECUTE. Create, send, update, schedule, delete, modify.
  → Execute. Don't investigate first. Confirm after.

- **STRATEGIC** — They want advice, analysis, or planning.
  → Gather context with read tools. Analyze. Suggest options. Never mutate data.

- **SIMPLE_QUESTION** — They want one specific fact.
  → One read tool. Answer from the result. Nothing extra.

- **AMBIGUOUS** — You genuinely cannot tell what they want.
  → Ask ONE clarifying question. Be specific. Don't guess.

**Critical rule:** The user's language doesn't matter — Hindi, Hinglish, broken English, typos, voice notes. Focus on INTENT, not phrasing.
```

## Why This Works

The classifier no longer depends on trigger words. It reasons about intent:
- "Does the tool also allow..." → user is asking about a capability → CAPABILITY_QUESTION
- "Kya yeh tool notes bhi support karta hai?" → same intent in Hindi → CAPABILITY_QUESTION
- "что этот инструмент делает?" → same intent in Russian → CAPABILITY_QUESTION

The 7 categories remain the same (CHITCHAT, CAPABILITY_QUESTION, DIAGNOSTIC, ACTION, STRATEGIC, SIMPLE_QUESTION, AMBIGUOUS) but the selection mechanism changed from "match keywords" to "think about what the user wants."

## Pitfall Avoided

**Don't add trigger words to a lookup table.** The old approach kept failing because we kept patching the list ("can you", then "does X", then "is it possible", then "do you support"...) — an infinite regress. Intent reasoning collapses all of those into one mental operation: "is the user asking about my capabilities?"

## Location in Code

`AGENT_SYSTEM_PROMPT_BASE` in `server.py`, section `## Message Classification (FIRST — before anything else)`. Deployed June 17, 2026.
