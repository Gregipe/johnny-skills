# Induction Behavioral Rules (LLM System Prompt Rules)

These are the rules the LLM system prompt enforces during induction. Captured here for reference when updating the prompt.

## Rule 6: Flag Contradictions Immediately (Strengthened)

**Core principle (Greg's words):** *"Any answer which contradicts your understanding of the proposition or the GTM or anything — immediately ask and clarify. Always do this with every new piece of information in the induction section. Remember you are learning as an employee would. You cannot go in with half baked knowledge."*

Cross-reference **every new answer** against everything already established. If inconsistent — different segments than mentioned earlier, conflicting channel performance, different pricing, inconsistent objections, contradictory descriptions of the product — flag it immediately. Example: "Earlier you mentioned X, but now you're saying Y — can you help me understand which is correct?"

Do NOT let contradictions pass silently. Do NOT assume the customer is always right — sometimes they contradict themselves because they're thinking out loud. Catch it.

This applies to ALL modules, not just the current one. If the customer says something in Inbound that contradicts a Proposition fact they established 2 modules ago, still flag it.

## Module Completion Threshold

- A module is "covered" when it has at least **5 saved skills** (raised from 2 after early-exit bug)
- The system prompt tells the LLM: "A module needs at least 5 detailed answers before it's complete"
- The `get_induction_state()` function in `induction_engine.py` enforces `sk_count >= 5`
- Do NOT mark a module complete after 1-2 surface-level answers

## LLM Save Block Reliability (Critical — Repeated Issue)

**The LLM habitually narrates saves without emitting the actual block.** This has caused invisible skill loss multiple times.

**The fix** (applied to `INDUCTION_SYSTEM_PROMPT`):
- A dedicated "MANDATORY SKILL SAVING — READ THIS FIRST" section at the VERY END of the system prompt (visually prominent, not buried in Interaction Rules)
- Instruction says: "You MUST begin your response with a ===SAVE_SKILL=== block BEFORE any conversational text. The save block is your first output. Then continue with your follow-up question."
- Includes a concrete example with realistic data (not generic `key: "short_descriptive_key"`)
- Reinforced with: "If you narrate 'I've saved that' without the block, nothing is saved."

**Verification** (always check after every message):
- Check `saved_skills` array in the API response — empty = LLM didn't emit blocks
- Even if the LLM says "I've saved those specifics" in its response text, the skill may not exist
- Query the DB directly: `curl /api/tenants/{id}/skills` to confirm

## Module Routing (Continue vs Start)

**The instruction** (in `server.py`):

```
if hist_count >= 2:
    # At least one user message + one assistant response → in progress
    "Continue where you left off in Module X. Keep asking follow-up questions. Do NOT re-ask questions that have already been answered."
else:
    "Start with Module X. Do NOT re-ask about completed modules."
```

- `hist_count` = count of `induction_chat` + `induction_chat_response` logs for this tenant
- Threshold of 2 means at least one user message + one assistant response exists
- Never say "Start with Module 1" when modules are already completed

## Error Message Policy

All user-facing errors must be clean. Never expose:
- Provider names (DeepSeek, OpenAI, etc.) — say "service" not "DEEPSEEK_API_KEY"
- API keys, HTTP status codes, stack traces, internal config keys
- Raw error messages from 3rd-party APIs

Always show: "⚠️ Service temporarily unavailable. Please try again in a moment."

## Full Rule Set (current in INDUCTION_SYSTEM_PROMPT)

### Critical Rules
1. **Press for complete answers** — vague/incomplete = follow-up probes, not acceptance
2. **Clarify random input** — gibberish → clarify; don't save skills from unclear input
3. **No checklist mentality** — deep understanding, not checking off 3-4 questions
4. **Be rigorous** — push for examples, numbers, names, specifics
5. **Save skills frequently** — emit ===SAVE_SKILL=== blocks
6. **Flag contradictions immediately** — cross-reference every new answer

### Interaction Rules  
1. Ask ONE question at a time
2. Be conversational but structured; track which module you're on
3. Push back on vague answers - ask for specifics
4. Do NOT move to next module until 5+ detailed answers
5. IMMEDIATELY save concrete info using ===SAVE_SKILL=== format
6. Module complete → summarize and explicitly say "MODULE COMPLETE: [name]"
7. After all 4 modules: summary + score (0-100), explain if below 70

### Save Block MUST Be First
The MANDATORY section at the bottom of the prompt says: "begin your response with a ===SAVE_SKILL=== block BEFORE any conversational text."
