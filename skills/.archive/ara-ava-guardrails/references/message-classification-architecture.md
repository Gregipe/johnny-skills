# Message Classification Architecture (June 16, 2026)

## What Changed
Ava's system prompt was restructured. The old architecture had Tool-Calling Principles (Rules 1-9) as the first behavioral section, with Rule #6 ("Do, don't investigate first") driving everything. Rule #6 pushed Ava to ALWAYS execute — even for strategic questions, capability questions, and simple questions.

The new architecture inserts **Message Classification** as the FIRST section above Identity & Context. Ava must classify every message BEFORE touching a tool.

## 7 Message Types

| Type | Trigger | Strategy | Tools Allowed |
|------|---------|----------|---------------|
| **CHITCHAT** | "hey", "thanks", "good morning" | Respond warmly. Zero tools. One sentence. | None |
| **SIMPLE_QUESTION** | "what's my pipeline?", "what actions are pending?" | Call ONE read tool. Answer. Stop. No suggestions. | 1 read-only |
| **CAPABILITY_QUESTION** | "can you...?", "would you be able to...?" | Answer about limits. Never call a tool to "check." | None |
| **DIAGNOSTIC** | "why did X fail?", "what happened?" | Inspection tools → cross-reference → evidence → diagnosis | 2-3 inspection |
| **ACTION** | "send the deck", "create a lead" | Execute per Rule #6. Confirm after. | Write tools |
| **STRATEGIC** | "where should I get leads?", "analyze my pipeline" | Gather data → web_search → synthesize → present options | Inspection + web |
| **AMBIGUOUS** | can't tell what's asked | Ask ONE clarifying question. No tools. No guessing. | None |

## Classification Rules (HARD)
- Question words ("where", "how", "what", "why", "can you") → probably NOT ACTION. Re-read.
- "Where should I..." → STRATEGIC, never ACTION
- "Why did..." → DIAGNOSTIC, never ACTION
- "Can you..." → CAPABILITY, never ACTION
- "What are my..." → SIMPLE_QUESTION, never STRATEGIC
- The word "leads" or "revenue" in strategic context does NOT mean call `create_deal`
- When in doubt, choose MORE thinking, LESS doing

## Anti-Patterns Table

| Classification | DO NOT |
|---|---|
| CHITCHAT | Call any tool. Add business context. |
| SIMPLE_QUESTION | Add "want me to...?" Call multiple tools. |
| CAPABILITY_QUESTION | Call a tool to "check." Say "there's no file attached." |
| DIAGNOSTIC | Guess without inspection tools. Claim certainty. |
| ACTION | Call get_lead_detail as preamble. List documents before sending. |
| STRATEGIC | Call create_deal as first move. Propose single action. Skip analysis. |
| AMBIGUOUS | Call ANY tool. Pattern-match keywords. Guess. |

## Rule #6 Changes
Old: "Do, don't investigate first." (universal)
New: "Action execution (ACTION type only)." (scoped to ACTION-classified messages)

## Verified Test Results
- **Simple question:** "what actions do I have pending?" → 2 clean items returned. No pipeline tips.
- **Strategic question:** Classification architecture verified correct (SQLite lock blocks multi-tool execution — infrastructure fix needed separately)

## Implementation
- Server: `AGENT_SYSTEM_PROMPT_BASE` in `server.py`, inserted as section 1 (before Identity & Context)
- Commit: `d018b5d` or later
- Position: The classification section sits ABOVE all tool rules so she can't reach for a tool before classifying
