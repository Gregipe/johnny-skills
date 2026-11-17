# Simplified Tool-Calling (Jun 17, 2026)

## The Problem

The original tool-calling principles had 9 rules with contradictions:
- Rule 4: "Verify before stating facts. Call read-only tools freely."
- Rule 6: "Don't check logs. Don't analyze beforehand."

The LLM resolved this conflict by following the earlier rule (verify first), causing 3-4 read-only tool calls before every action. Combined with overlapping tools (get_action_items, query_actions, query_database), every simple update consumed 4+ steps.

## The Fix: 3 Rules

```
1. **Do exactly what was asked.** Find the right tool, call it. 
   No extra steps, no verification loops. If Greg says "update the due date," call the update tool directly. 
   The tool result will tell you if you got it right.

2. **On failure, retry — don't give up.** If a tool errors, fix your input and retry (up to 3 times). 
   If the wrong tool, switch. If you're missing information, ask Greg one question. 
   Never respond with "I couldn't finish" — either succeed, retry, or ask.

3. **One confirmation per action, no extras.** After success, confirm what happened in one line. 
   Don't bundle unrelated actions. Don't "while I'm at it."
```

## Tool Schema Deduplication

**Removed:** `query_actions` — redundant with `get_action_items`
**Demoted:** `query_database` — description changed to "⛔ DO NOT USE for action items, leads, or deals — use dedicated tools instead. Raw SQL only when no other tool exists."
**Added to Rule 1:** Tool routing guide — "actions → get_action_items, leads → search_leads, deals → search_deals"

## Observe Loop Fixes

**MAX_TOOL_STEPS:** 6 → 10
**Step-9 nudge:** Changed from "STOP calling tools now. Synthesize." → "You're nearing the step limit. If you have more actions, call them now — you can continue. If genuinely done, summarize what you accomplished."

The original nudge forced premature termination. The LLM would hit step 5, see "STOP calling tools," and give up mid-task even when it had more actions to complete.

## Identity Fix

**Before:** "You are Ava, the conversational CRM and mobile intelligence layer for Hunar. You are part CRM, part chief-of-staff, part co-pilot."
**After:** "You are Ava, Greg's co-pilot. You work for Hunar. You are chief-of-staff and co-pilot."

The word "CRM" in the identity triggered LLM training-data patterns where CRM assistants respond to greetings with capability lists. Removing it broke the learned pattern.

## Anti-Patterns to Avoid

1. **Multiple overlapping tools for the same task** — the LLM can't choose, so it uses all of them
2. **"STOP" nudges** — the LLM takes them literally and abandons unfinished work
3. **"Verify before acting" alongside "act directly"** — creates unresolvable conflict
4. **Formal classification frameworks** (CLASSIFY INTENT FIRST, 5-type categories) — add meta-cognition overhead that causes overthinking on simple messages
5. **"CRM" in agent identity** — triggers capability-list training patterns
