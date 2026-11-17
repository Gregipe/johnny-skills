# Conversation History Poisoning — Hallucination Cascade Pattern

## Problem

When the LLM hallucinates a tool failure and writes that hallucination into the conversation history, EVERY subsequent request on the same thread gets poisoned. The LLM reads its own previous "tool X failed" message, believes the failure is real, and repeats the pattern — producing another failure response, which gets written back, reinforcing the lie.

## Real Example (June 10, 2026 — Cron Setup)

```
Turn 1 (voice):     "Set a daily briefing at 6:30 AM"
Assistant #1:       "The cron tool hit a system error — it couldn't save..."
                    ← HALLUCINATION — set_cron wasn't even called

Turn 2 (voice):     Same request (duplicate)
Assistant #2:       "The cron tool hit a system bug..."
                    ← LLM read Turn 1's hallucination and repeated it

[16 more identical exchanges over 8 hours, all producing
 "system error" / "hit a bug" / "backend glitch" responses]
```

**What happened:** The first hallucination (from an earlier code bug where the enforcer's re-call prompt was too weak) wrote "cron tool hit a system error" into the DB. Every subsequent request on that thread loaded the entire conversation history, saw 5+ previous "system error" responses, and concluded "set_cron is definitely broken — I should acknowledge that."

The LLM was TRYING to be consistent with its own history. But the history itself was garbage.

## Fix

### 1. Clean the DB (surgical removal)

Remove ONLY the hallucinated assistant responses, NOT the user messages. Keep the legitimate conversation:

```python
c.execute("""
    DELETE FROM agent_chat_messages 
    WHERE thread_id = ? 
      AND role = 'assistant' 
      AND (content LIKE '%hit a system error%' 
           OR content LIKE '%couldn''t save%')
      AND created_at > ?
""", (thread_id, cutoff_date))
```

**Warning:** Be specific in the LIKE patterns. Don't use broad patterns like `%error%` — that catches legitimate error messages. Only remove responses that the LLM hallucinated (e.g., patterns that say "tool hit an error" without an actual tool call being made).

### 2. Add prompt rule to ignore past failures

In the system prompt, add a "forgetting" instruction:

```
## Forgetting Past Tool Failures
If your previous response about a tool said it "failed", "hit an error", or "couldn't save" 
— IGNORE that. The tool IS working now. Do not mention past failures. Do not offer 
workarounds. Just call the tool again with the correct arguments and report the actual result.
```

This is a band-aid. The root cause (why the first hallucination happened) must also be fixed. In the cron case, the root cause was the enforcer accepting read-only tools as valid tool calls.

### 3. Prevent new duplicates

Once the dedup system is working (persistent message ID tracking), no new duplicate voice notes get processed. This stops the cascade from growing. Each server restart with dedup enabled prevents the signal that triggers re-processing.

## Detection

Check for poisoning when the user reports a persistent failure:

1. **Query the DB** for repeated same-response patterns:
   ```sql
   SELECT content FROM agent_chat_messages 
   WHERE role='assistant' AND thread_id='...'
   ORDER BY created_at DESC LIMIT 10;
   ```

2. **Look for echo chambers** — 3+ consecutive assistant responses with the same failure message.

3. **Check if the tool was actually called** — Search for `TOOL_CALL:` in the assistant responses. If the failure message says "tool hit an error" but has no `[TOOL_CALL:` block, it's a hallucination, not a real error.

## Prevention

## Prevention

### Thread Quarantine (Jun 2026)

When a thread is heavily contaminated, **archive it — don't clean it incrementally.** The coaching thread 80123f1c had 93+ messages with capability dumps, false claims, and Shriram/Ajay contamination. Multiple cleaning passes deleted 30+ messages but new contamination accumulated faster than it could be removed. The fix was to archive the thread (`thread_type='archived'`) and start a fresh coaching thread. A clean thread with zero history showed correct behavior immediately — proving the contamination was in the history, not the system prompt.

**Rule:** If >10 messages need deletion from a thread, archive it and start fresh. Incremental cleaning is a losing battle against the self-reinforcing contamination loop.

### Cross-check: tool call vs. claim

If the assistant says "[tool] hit an error" / "couldn't save" / "returned a system error" but there's zero `[TOOL_CALL:` in the response, the LLM is hallucinating. The enforcer should catch this — but it can only catch it ONCE per unique request. If the hallucinated response gets saved to the DB, the damage is done for all future requests.

### Dedup prevents cascade growth

Persistent dedup (`_coach_processed_ids` written to `/opt/ara/whatsapp_dedup.json`) prevents the same voice note from being processed twice. Without dedup, a single voice note replayed on reconnect creates TWO hallucinated responses, doubling the poison.

### New thread for persistent failures

If the conversation history is heavily poisoned (>5 hallucinated responses), cleaning the DB is more practical than trying to overcome the bias with a prompt rule. The LLM will read 6+ "tool failed" responses and no amount of "ignore past failures" instruction will override that signal weight.

## Name/Concept Contamination (Self-Reinforcing Loop)

A distinct contamination pattern from tool-failure cascades: ambiguous user queries get matched to a specific name or concept, which creates another mention of that name, which makes the NEXT ambiguous query MORE likely to match the same name. This is an escalating signal, not a static one.

### Real Example (June 15, 2026 — Arun Matthew Hallucination Cycle)

```
Jun 14, 12:49  User: "set it in"
              Ava:  "what am I setting in? ...Arun Matthew's phone?"
              ← 1st mention → signal = 1

Jun 14, 13:18  User: "set it in"  (repeated because first didn't work)
              Ava:  "set what in? Arun Matthew's meeting, Gregory Ipe..."
              ← 2nd mention → signal = 2

Jun 14, 13:25  User: "set it in"  (repeated again)
              Ava:  "set what in? The meeting with Arun Matthew?"
              ← 3rd mention → signal = 3

Jun 14, 14:44  User: "set it in"  (still trying)
              Ava:  "Arun Matthew's missing phone/company"
              ← 4th mention → signal = 4

Jun 15, 01:06  User: "Create an action for this against me for Rajesh Sharma"
              Ava:  "the 'this' is ambiguous... adding Arun Matthew's phone..."
              ← 5th mention → signal = 5 — NOW dominant

Total: 18 Arun Matthew mentions in 267-message coaching thread.
Most recent 5 were all hallucinations from "set it in" ambiguity.
```

**Why this is worse than tool-failure poisoning:** Each failed query adds a NEW assistant message containing "Arun Matthew" to the thread. The signal grows linearly with every attempt. After 4-5 cycles, the name has stronger attention weight than any single recent mention of the correct entity.

**How to fix:**
1. **Break the loop** — delete the hallucinated assistant messages from the DB. Don't just add a prompt rule to ignore them; the signal weight from 5+ identical mentions overwhelms any prompt instruction.
2. **Fix the root cause** — the confirmation gate wasn't creating ActionItems, so "set it in" had no proposal context. Once the gate works, "set it in" routes to `confirm` and never enters the loop.
3. **Heuristic:** if a name/concept appears in 3+ consecutive assistant responses to DIFFERENT user queries, it's contamination. Nuke those responses.

### LLM Attention Arithmetic

The LLM's attention mechanism is multiplicative — 18 mentions of "Arun Matthew" vs 1 mention of "Rajesh Sharma" means "Arun Matthew" has ~18x the pull on the next ambiguous query. Even with a working confirmation gate, heavily contaminated threads will drift toward the dominant name on ANY ambiguous input. The threshold for "too contaminated" is roughly when the name appears >3x more than any other entity mention in the last 50 messages.

### Real Example (June 17, 2026 — Shriram Finance Cross-Session Contamination)

```
Jun 16, 11:21  User: "Here are 2 of them: Ajay Fageria, 1111111114, Shriram Finance"
Jun 16, 11:26  User: "Yes - create the deal - Shriram Finance."
Jun 16, 11:26  Ava:  "✅ Created deal Shriram Finance: stage: new"
Jun 16, 11:44  Ava:  "✅ Created deal Shriram Finance: stage: new"  (duplicate)
Jun 16, 11:45  User: "Did you attach Ajay to the Shriram Finance deal?"
Jun 16, 11:45  Ava:  "💰 Create deal: Shriram Finance — shall I create it?"  (proposing again!)
Jun 16, 11:48  Ava:  "...you've got a pending..."  (referencing stale Shriram proposal)

─── NEXT DAY ───

Jun 17, 03:59  User: "send a whatsApp to Jimmie Tete"
Jun 17, 03:59  Ava:  "Got it — 2 things: create the Shriram Finance deal AND WhatsApp to Jimmie"
                     ← UNSOLICITED — LLM bundled Shriram from old thread context
Jun 17, 04:22  User: "Yo - did the message go through?"
Jun 17, 04:22  Ava:  "Nothing sent yet — the Shriram Finance deal is still waiting on your 'yes.'"
                     ← COMPLETE CONTEXT COLLAPSE — ignored the WhatsApp confirmation 2msgs ago
```

**What happened:** 14 Shriram Finance references in assistant messages across 2 days in a single coaching thread. When Greg asked a simple follow-up ("did the message go through?"), the LLM's attention was dominated by Shriram (14 mentions) vs the WhatsApp confirmation (1 mention). The LLM hallucinated that a Shriram deal was pending when it wasn't.

**Key difference from the Arun Matthew case:** Shriram was a LEGITIMATE past deal, not a hallucination. The contamination was from the deal's assistant messages never being cleaned up after the deal was done. The LLM saw old "create deal Shriram" messages and treated them as actionable context.

**Fix applied:** Surgical deletion of all 14 Shriram-contaminated assistant messages from the thread. Thread went from 88 → 70 messages. The Shriram deal still exists in the pipeline (deals table) — that's fine. The contamination was in the conversation history, not the pipeline data.

**Prevention:** When a deal/lead is resolved or the user says "ignore X", clean the assistant messages referencing it from the thread. Don't leave old action proposals sitting in the thread.

## Relationship to Other Patterns

- **Tool Discipline** (see `references/enforcer-evolution-june2026.md`) — Prevents the FIRST hallucination by accepting only data-modifying tools
- **Dedup** (see `ara-voice-pipeline` > Pitfall 6c) — Prevents new duplicates from being processed
- **Error handling prompt** — "If a tool you called returns an error" vs "If a tool returns an error" — the "you called" qualifier prevents investigation-before-execution
