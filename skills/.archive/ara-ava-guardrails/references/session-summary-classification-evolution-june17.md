# Ava Intelligence Upgrades — June 17, 2026 Session

## Classification Evolution (3 iterations in one session)

### Iteration 1: Keyword-matching → 7-category intent reasoning
Greg explicitly rejected keyword-matching: "If I have a set of terms that she matches, she is not powerful." The old approach listed trigger phrases ("can you", "does X") — every unlisted phrasing broke classification.

### Iteration 2: 7-category checklist → pure intent reasoning
Greg rejected the checklist too: "Again is this the same way that you reason by asking yourself seven ordered questions?" The 7 questions were scaffolding — a proxy for understanding that still failed at edges.

### Iteration 3: Final — single instruction
```
Read Greg's message. Think about what he wants. That's your entire classification.
Then respond accordingly.
```
No categories, no triggers, no checklists. Same as Johnny's approach. All safety nets preserved (hard guard, anti-patterns, meta-cognition, search-before-guessing).

## Session Summary Hallucination (Fixed)

**Failure:** "Hey Ava! Could you give me a crisp 3-4 line summary of what we've discussed in this entire session?" → Ava proposed marking Jimmie Tete's "Send Infosec" as resolved. Complete context contamination.

**Root cause:** Thread context contained overdue Jimmie Tete action. Ava treated thread history as actionable data, not as a conversation to reflect on. No meta-cognition.

**Fix:**
1. SIMPLE_QUESTION expanded to include session recap requests
2. Meta-cognition rule: "When asked about the conversation itself, step outside it. Never propose actions."
3. Anti-pattern added: "Summary request → action proposal"

**Why Johnny doesn't fail:** Johnny has native meta-cognition — he steps outside the conversation and reflects on it as a whole when asked.

## Conversation History Search (search_conversation_history)

Built to solve the "what tool were we discussing?" follow-up problem. FTS5 on agent_chat_messages. Two layers:
1. Thread injection (last 10 messages) for immediate context
2. search_conversation_history tool for references beyond the window

Prompt rule: "Search before you guess." A 50ms FTS5 search is cheaper than a wrong answer.

## WhatsApp Cross-Channel Context

WhatsApp now has thread identity (phone → ChatThread) + context injection (last 10 messages). Same pattern extendable to Telegram/Slack/Discord via webhook adapter.

## Design principle: Ava should reason like Johnny

The entire session converged on this: Ava's classification now matches Johnny's ("think about what Greg wants"), she has search tools for context, and she has meta-cognition for reflection. The remaining gap is native conversation understanding vs scaffold-based proxies.
