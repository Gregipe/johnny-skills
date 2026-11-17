# Agent Chat Tier Classifier — Intent-Based (June 17, 2026)

**Problem:** The original tier classifier (smalltalk/status/command) defined each tier by
example trigger words: "update", "send", "create"... for command. A command phrased without
an imperative verb — "Rajesh's deadline should really be Friday" — contained no trigger
word and was mis-tiered as status, after which the model lacked full pipeline context.

**Location:** `agent_chat` in `server.py`, the tier classification prompt (~line 6618).
Used for the conditional context-injection tiering (Fix 1 + Fix A).

## The Prompt (Deployed)

```
Classify this CRM user message into exactly one word:

smalltalk — greeting, thanks, acknowledgment, or chitchat with no request
            and no question about the pipeline.
status    — the user is asking about existing state and wants only to be
            told something (what exists, what happened, what's due).
            Pure information request, no change implied.
command   — the user wants something created, changed, sent, scheduled,
            or done — including indirect or declarative phrasing
            ("X should be Friday", "Acme really needs to move to
            qualified", "let's get Rajesh a follow-up"). If the message
            implies a desired change to state, even without an imperative
            verb, it is command.

Tie-break: if it is ambiguous whether the user wants information or a change, classify as command.
Reply with one word only: smalltalk, status, or command.
```

## Design Choices

1. **Intent-based, not keyword-based.** Tiers are defined by what the user wants done,
   not which words they used. Declarative commands ("should be", "needs to move") are
   command, not status.

2. **Command-biased tie-break.** Ambiguous → command. A command mis-read as status fails
   to act (bad, user-visible); a status mis-read as command over-supplies context (cheap,
   harmless). The asymmetry is deliberate.

3. **One-token output, temperature 0, strict parse.** Fail-open default to command on
   error or unrecognized output — never starves a real command of context.

4. **Separate from Ava's prompt-based classifier.** This is a dedicated LLM call
   (`call_llm` with a short prompt, not part of the main observe-loop system prompt).
   Ava's 7-category classifier (in `AGENT_SYSTEM_PROMPT_BASE`) is different — it
   routes conversation inside the observe loop. This classifier decides which context
   blocks to inject BEFORE the loop starts.

## Verification Tests

- "what's overdue?" → status ✓
- "update Amardeep's deadline to 8pm" → command ✓
- "Hi Ava" → smalltalk ✓
- "Rajesh's deadline should really be Friday" → command (declarative, no imperative verb) ✓
- "I think Acme should move to qualified" → command ✓
- "is Rajesh's reminder set for Friday?" → status (genuine question, no change wanted) ✓

The last test is the load-bearing overcorrection guard — proves the command bias
didn't swallow real questions into command.

## Pitfall Avoided

**Don't add trigger words.** The original keyword approach kept failing because
declarative commands lack trigger words. Adding more words ("should", "needs to",
"really") is an infinite regress. Intent reasoning collapses all variants into
"does the message imply a desired change to state?"

## Related

- Fix 1 + Fix A: conditional context injection (smalltalk gets nothing, status gets
  recent-actions, command gets full pipeline)
- Fix B commit: 26e5c15
