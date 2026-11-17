# CLASSIFY INTENT FIRST — June 2026 Rewrite

## The Problem

The old prompt scattered classification rules across 7 different sections ("How to respond", "Reasoning Preamble", "Simple Questions", "Anti-Patterns", "Tool-Calling Principles"). None were strong enough individually to resist the pipeline data's pull. Result: the LLM defaulted to pipeline-action mode for ambiguous inputs.

## The Solution

A single, unified classification framework that the LLM executes BEFORE looking at pipeline data or tools.

### Five Intent Types

| Type | Definition | Action Rule |
|------|-----------|-------------|
| **QUESTION** | Greg wants information. NOT asking you to do anything. | Answer directly. No tools (unless read-only lookup helps). Never follow up with "want me to...?" |
| **COMMAND** | Greg named a specific action and target. | Plan the exact action. Call only matching tools. Do NOT add extras. "Send a WhatsApp" does not mean "create a deal too." |
| **HYPOTHETICAL** | Greg is asking whether you COULD do something. "Would you be able to...?" / "If I asked you..." | Answer directly: "Yes, I can do that by..." or "No, because..." Never "demonstrate" by doing it. This is a QUESTION, not a command. |
| **CONVERSATION** | Greeting, chatting, or asking about the conversation. "Hey" / "Summarize this session" | Respond naturally. For summaries, step outside the conversation and reflect. Never propose actions. |
| **AMBIGUOUS** | Cannot tell what Greg wants after thinking. | Ask ONE clarifying question. Never guess. Never pattern-match keywords into tools. |

### Reasoning Preamble

After classifying, state the classification in one line:
"Got it — [TYPE]. Greg wants [X]. I'll [plan]."

Examples:
- "Got it — QUESTION. Greg wants to know if I can create deals with contacts. I'll answer directly."
- "Got it — COMMAND. Greg wants a WhatsApp sent to Jimmie. I'll call send_whatsapp."
- "Got it — HYPOTHETICAL. Greg is asking whether I could handle multi-step creation. I'll explain, no tools."
- "Got it — CONVERSATION. Greg wants a session summary. I'll synthesize from thread history."

### Every Old Anti-Pattern Maps to Misclassification

- "Capability question → tool call" = misclassifying HYPOTHETICAL as COMMAND
- "Greeting → business pitch" = misclassifying CONVERSATION as COMMAND
- "Vague reference → assumption" = misclassifying AMBIGUOUS as COMMAND
- "Advice request → single action" = misclassifying QUESTION as COMMAND

## Pattern-Matching is FORBIDDEN

**Greg's explicit directive (June 17, 2026):** "No more pattern matching; it will lead to error. I need the LLMs to step in."

The classification framework uses LLM reasoning — NOT regex, NOT keyword lists, NOT hardcoded English phrases. A `_is_hypothetical_question()` function with regex patterns was written, deployed, and immediately reverted after Greg's pushback. The fix is always in the prompt, not in code.

## Pipeline Data Overwhelms Classification

**Critical architectural insight (June 2026):** Ava's context contains 13+ leads and 12+ deals injected every turn. This pipeline data is the most salient content in her context window — more attention-grabbing than the classification rules. When the user says anything ambiguous ("hey Ava", a voice note, "Hi Ava"), the LLM defaults to the most salient pipeline names.

This creates a **self-reinforcing contamination cycle:**
1. Pipeline injects "Ajay Fageria | Shriram Finance | new" (alphabetically first in "new" stage)
2. LLM proposes creating them → hallucinated Assistant message saved to thread
3. Thread gets contaminated with Ajay/Shriram references
4. Next turn: EVEN MORE attention on Ajay/Shriram
5. Cycle accelerates until thread is nuked

### Why Johnny Doesn't Have This Problem

Johnny's context has NO pipeline data. His tools (terminal, research, delegation) cannot act on CRM. His constraints are structural — he *can't* create deals, so he never considers it. Ava's constraints must be intentional — she must *choose* not to act.

### Two-Pass Classification (Proposed)

The only way to give Ava Johnny's classification discipline:

1. **Pass 1:** LLM call with NO pipeline data, NO tools — classify intent only
2. **Pass 2 (COMMAND only):** LLM call WITH pipeline + tools — execute the command
3. **All other types:** Answer from Pass 1 directly, no second call

This was proposed June 17, 2026 but not yet deployed.

## Deployed Fixes (June 17, 2026)

Three code-level defenses deployed alongside the prompt redesign:

1. **Single-action guard** (`_guard_single_action`): Scans user message for action verbs. If exactly ONE verb found but LLM proposed MULTIPLE tools, auto-trims to matching tool only. Catches "send WhatsApp to Jimmie" → drops "create Shriram deal."

2. **Partial confirmation** (`_split_partial_rejection`): Handles "ignore X, do Y" replies. Splits pending tool calls: rejected tools dropped, kept tools executed. Catches "Ignore the shriram finance deal and just handle the whatsApp."

3. **Conversation history poisoning cleanup**: See `references/conversation-history-poisoning.md` for the pattern and `references/thread-cleanup-protocol.md` for the surgical DB deletion methodology.

### ToolResult.fail() Bug

`search_conversation_history` was calling `ToolResult.fail(tool, message)` with 2 args instead of 3 `(tool, code, message)`. Fixed by adding `"MISSING_ARG"` and `"SEARCH_FAILED"` error codes. This caused LLM to receive malformed error responses when trying to search past conversations.
