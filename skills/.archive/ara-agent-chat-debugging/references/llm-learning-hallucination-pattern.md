# LLM Learning Hallucination Pattern — Fabricated Case Studies & Data

## Symptom

Ava says: *"I have 10 new learnings in the queue today — mostly centered around a powerful Acme Corp logistics case study…"* and lists specific metrics (65% reduction, 40% decrease, 85% preference, etc.).

None of these items exist in the database.

## Root Cause

When the `search_knowledge_base`, `skills` table query, or learning notifications return **empty results**, the LLM fills the gap with plausible-sounding fiction. It knows:

- Hunar does logistics/recruitment → invents "Acme Corp" as a client
- Case studies have metrics → invents specific numbers (65% reduction, 40% decrease)
- Plan features are discussed → invents "voice-to-voice AI engine included in all plans"

The LLM does this because its training biases it toward being **helpful** — it would rather produce content than say "I have nothing." The system prompt doesn't explicitly forbid fabricating data, and the "Data Honesty" rule is about missing fields (phone, email) not about fabricated narratives.

## Diagnosis

```bash
# Check the skills table for specific learnings
sqlite3 ara.db "SELECT category, key, value FROM skills ORDER BY id DESC LIMIT 20;"

# Check documents table
sqlite3 ara.db "SELECT filename FROM documents ORDER BY id DESC LIMIT 10;"

# Check insights/learnings
sqlite3 ara.db "SELECT insight_type, summary FROM ava_insights ORDER BY id DESC LIMIT 10;"
```

**Key question:** Is there ANY row containing the claimed data? If not → hallucination.

## Fix

### Immediate (Prompt-Level): Add Anti-Hallucination Guard

In the system prompt's Guidelines section, add:

```
NEVER invent case studies, metrics, numbers, or client stories. If the database 
returns nothing or you're unsure, say "I don't have anything on that" or 
"I don't see any learnings in the queue."
```

This must be positioned **near the data that triggers the hallucination** (the skills/induction/documents context section), not buried in a general Guidelines block.

### Structural (Code-Level): Block Fakery in the Prompt Context

In `build_system_prompt()` in server.py, modify how empty data is presented to the LLM:

```python
# BEFORE — LLM fills the gap with fiction
skills_context = "\n".join([f"- {s.key}: {s.value}" for s in skills])
if not skills_context:
    skills_context = "No skills/learnings have been added yet."

# AFTER — Explicitly tells the LLM nothing was found
skills_context = "\n".join([f"- {s.key}: {s.value}" for s in skills])
if not skills_context:
    skills_context = "NONE — no skills have been saved yet."
```

The word "NONE" is more definitive than "No X have been added yet" — it's a less natural prompt for the LLM to override.

### Verification

1. Trigger the flow that normally produces hallucinations (ask Ava about learnings with empty DB)
2. Response should be: "I checked the learnings — there's nothing in the queue right now."
3. Confirm no metrics, case studies, or fabricated numbers appear

## Second Failure Mode: No Tool Call + Implied Technical Failure

**A separate failure mode emerged on June 4, 2026** distinct from the fabricated case study pattern. When asked "What did you learn yesterday evening?":

1. **No tool call at all** — Ava didn't invoke `search_knowledge_base` or any endpoint
2. **"System tried to pull a summary"** — Response: *"No new learnings were logged yesterday evening — the system tried to pull a summary but it didn't come through cleanly."*
3. This violates the Data Honesty rule (no "couldn't retrieve" / "failed to load" framing)

**Why this is different from the case study pattern:**
- Case study pattern: LLM has data and fills in fake numbers (Active fabrication)
- No-tool-call pattern: LLM skips the tool entirely and answers from context (Passive fabrication — just makes something up without checking)

**Root cause: the anti-hallucination rule was buried in Data Honesty.** The LLM treated "call a tool before stating facts about learnings" as a sub-bullet about *formatting data* (like "not on file" vs "failed to load"), not as an imperative to *call a tool before speaking*.

**Diagnosis:** Check server logs (or proxy logs) for `POST /api/agent/chat/...` responses. If no DeepSeek tool-call tokens appear between the user message and the final response, the LLM didn't call a tool — it answered from context. You can also grep the server output for `search_knowledge_base` or `Tool 'search_knowledge_base':` — if absent, no tool was called.

Another sign: the server logs show only ONE DeepSeek API call (no tool execution → no follow-up LLM call). A tool-first response produces TWO calls: one to generate the `[KB:]` shorthand, one to synthesize the result.

**Fix deployed (June 4, 2026):** Three changes in `server.py` solved this:

**Change 1 — New `## Tool-First Policy (HARD RULE)` section (line 4844):**
Placed right after Pipeline context (leads/deals data dump) and before Workflow: Sending Messages. Position 3 in the prompt, after the inline data the LLM might be tempted to rely on:

```python
## Tool-First Policy (HARD RULE)
You MUST call **search_knowledge_base** before answering any question about
learnings, knowledge, or recent activity — even if the INDUCTION line above
shows data. Inline context is static; the tool reflects the actual current state.

When user asks about learnings/knowledge, output `[KB: topic]` to search
knowledge base (e.g., `[KB: yesterday]`, `[KB: recent learnings]`).
Then STOP and wait for the result.

If tool returns nothing → say exactly: "I don't have any learnings right now"
If tool returns results → summarize what the tool said, nothing more.

**If the question references a specific time** ("yesterday", "recently",
"last week") — call the tool first. Do NOT rely on context you already have.
Inline context may be stale.

Violation = false information. This rule overrides all other instructions.
```

**Change 2 — `[KB:` shorthand parser added (line 5176):**
```python
kb_match = re.search(r'\[KB:\s*(.*?)\]', response)
...
if kb_match:
    tool_calls.append(("search_knowledge_base", {"query": kb_match.group(1).strip()}))
```
Also added `KB` to the response_clean regex so it's stripped from user-facing text.

**Change 3 — Data Honesty section slimmed (line 4879):**
The verbose CRITICAL anti-hallucination block was replaced with a cross-reference:
```
**See Tool-First Policy above — call a tool before stating any fact. Never invent data.**
```

**Why `[KB:]` instead of `[TOOL_CALL: {"tool":...}]`:**
- The JSON format with braces caused `KeyError: '"tool"'` from Python's `.format()` — example strings inside the prompt must use `{{` / `}}` escaping, which makes the prompt harder to read and edit
- A 3-character prefix is much easier for the LLM to output reliably
- Follows the same pattern as the existing `[SEARCH: query]` shorthand for `web_search`

**Live verification (June 4, 2026):**
```
User: "What did you learn yesterday evening?"
Ava: "I checked the knowledge base, Greg — nothing recorded from yesterday
      evening. So no new learnings to report. Want me to recap where things
      stand on your leads instead?"
```
- ✅ Called `search_knowledge_base` (confirmed by two DeepSeek API calls in logs)
- ✅ No "system tried to pull a summary" phrasing
- ✅ No invented case studies or metrics
- ✅ Clean "nothing recorded" framing — missing data is normal

**What was tried and discarded:**
- Putting the `[TOOL_CALL: {"tool":...}]` JSON example in the prompt — caused KeyError from unescaped braces in `.format()`. The `[KB:]` shorthand sidesteps this entirely.
- Position 2 (right after Identity, before Tone) — not tested because KeyError hit first. Position 3 works.

**Key insight for future fixes:**
A `[KB:]` shorthand is essential — the model won't reliably output verbose JSON tool calls for read-only queries. Follow the existing `[SEARCH:]` pattern. Also: always clear `__pycache__/*.pyc` after editing prompt strings, or stale bytecode will cause KeyErrors that point at the current source (misleading).

**Key insight:** Burying behavioral rules inside "formatting" sections guarantees they'll be ignored. If you want the LLM to DO something before responding, the instruction must be at the top of the prompt — not in a sub-section about how to describe data.

## Pitfalls

1. **LLM is extremely resilient to "say nothing" instructions.** Even with explicit rules, it may still fabricate. The fix may need to be code-level (server detects and blocks fabricated-looking content).
2. **Don't over-block.** The induction module legitimately has skills from conversations, documents, and prompts. The check is for hallucinated *narratives* (case studies with metrics), not for the existence of skills entirely.
3. **Cross-check timestamps.** If Ava claims "10 new learnings," check if `skills.updated_at` or `ava_insights.created_at` are > last conversation time. If all timestamps are weeks old, the "new learnings" claim is fabricated.
4. **Burying a "call tool first" rule in Data Honesty = same as not having it.** The LLM reads section headers for scope. "Data Honesty" sounds like it governs *how to describe existing data*, not *whether to call a tool before describing it*. Position-dependent LLM behavior means the rule MUST be at the top — this is not a cosmetic choice.
