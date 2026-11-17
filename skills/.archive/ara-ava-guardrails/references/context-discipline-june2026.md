# Context Discipline — The "Remove, Don't Add" Principle

**The single most important rule for Ava's prompt engineering:** every guard, nudge, correction, or instruction injected into context displaces the original user message. The cumulative effect causes context loss, over-attention to salient injected text, and unpredictable behavior. When facing a misclassification or wrong-action problem, **remove text, don't add it.**

## The Core Problem

The LLM attends to the most salient text in its context. When you inject pipeline data + guards + nudges + mode reminders, the original user message gets buried under layers of injected text. The injected text then becomes the most salient thing, and the LLM responds to THAT instead of the user.

### The Nudge Spiral

```
Turn 1: "Hi Ava" → LLM produces capability dump → claim-nudge fires → 
        90-word correction injected → pushes "Hi Ava" 3 positions back
Turn 2: Next message → LLM sees 90-word nudge → attends to it → 
        produces worse output → MORE nudges fire → context balloons
```

By turn 3-4, `loop_messages` is: `[system_prompt(huge), 50 history msgs, user_msg, assistant_1, tool_1, NUDGE, assistant_2, tool_2, NUDGE, assistant_3, ...]`. The original intent is buried.

## Case Study 1: Classification Framework Reversion

**Problem:** The CLASSIFY INTENT FIRST framework (5 categories, 50+ lines) made every message a classification task. "Hi Ava" → *"Greg is asking a QUESTION about what I can do"* — the classification instructions were the most salient text.

**Fix:** Reverted to: *"Read Greg's message. Think about what he wants. No categories, no triggers, no checklists. If he's greeting you, greet back warmly."* — 5 lines. Greetings fixed instantly.

**Lesson:** Classification frameworks are self-defeating. They add text that the LLM attends to INSTEAD of the user's message.

## Case Study 2: Regex Guard Deletion

**What was deleted (June 2026):**
- `_claims_action_without_call()` — 4 regex families detecting "I've updated", "Shall I set", "Sound right?"
- `_action_map` — 12 verb→pattern mappings cross-checking tool calls against prose
- `_analysis_mode` — 3 keyword sets detecting "strategic", "diagnostic", "capability" modes
- Mode reminders — re-injected on every loop iteration
- `_parse_tool_calls()` legacy fallback

**What replaced them:** One sentence in Tool-Calling Principles: *"Never describe a write as completed unless the tool result confirms it."*

**Result:** 200+ lines of code and 4 injected-text patterns removed. Context displacement eliminated. The claim-without-call problem was solved by removing the gap between prose and tools, not by detecting it after the fact.

## Case Study 3: Tiered Context Injection

**Problem:** Full pipeline data (13 leads + 12 deals + action items + integrations) injected on every message. "Hi Ava" got the same context as "update the Amardeep deadline." The most salient pipeline item (alphabetically-first new lead) got parroted.

**Fix:** Cheap LLM classification call (temperature 0, three-word output) tiers messages:
- **smalltalk** → identity + personality + time only. Zero pipeline data.
- **status** → recent-actions block only. No lead/deal dump.
- **command** → full pipeline (current behavior).

**This shrinks context for the ~80% of messages that aren't commands.** Directly prevents capability dumps, Shriram/Ajay proposals, and spurious lead creation from voice notes.

## Architecture Rules

1. **Tiered context injection** — don't inject what the message doesn't need.
2. **Prose-after-result** — never describe an action as done without tool confirmation.
3. **Thread quarantine** — archive poisoned threads; never let them accumulate.
4. **Remove redundant tools** — when get_action_items, query_actions, and query_database all find the same thing, the LLM calls all three. Remove the overlap.
5. **Confirmation short-circuit must be verified** — the confirm path executes stored pending_tool_calls directly and returns without re-entering the observe loop. If it falls through, the model re-evaluates against the full pipeline. Verify, don't rebuild.
6. **Sidecar durability requires inbox-first** — messages must be durably stored (SQLite) before any filtering or routing. pending.json replay only covers messages already received; messages arriving during reconnection are lost without inbox-first.
7. **Partial snapshots must declare themselves** — when injecting a capped data block (like 7-row recent-actions), the header must explicitly warn the model the block is INCOMPLETE and specify when it must reach for a tool for completeness. Silent data loss (under-querying) is worse than visible inefficiency (over-querying).
8. **Within-turn read cache** — when the observe loop is several steps deep, the model re-fetches data it already retrieved because prior results scroll out of its attention window. A per-turn cache keyed on (tool_name, json.dumps(args)) deduplicates identical read-only calls within a single turn. Read-only tools only; never cache writes. This is NOT a text-injection guard — it prevents literal redundant work, not inferred intent.
9. **Per-tier block injection** — the recent-actions block must ONLY be appended inside the status and command branches. Never inject it unconditionally after the tier check — that half-reintroduces the salience problem Fix 1 was built to eliminate by giving smalltalk live action data it shouldn't have.

## Case Study 4: Two-Pass Classification Failure

**Problem:** Pass 1 (minimal prompt) → Pass 2 (full pipeline + tools) was supposed to keep simple messages low-context. Instead, Pass 1's classification prompt became the most salient text and caused overthinking. "Hi Ava" still produced capability dumps because the Pass 1 prompt said "If Greg is asking you to DO something, start with COMMAND." The word "DO something" primed the LLM to look for things to do.

**Fix:** Reverted to single-pass. The tiered context injection (Case Study 3) achieves the same goal — light context for light messages — without a separate classification pass.

**Lesson:** Adding a classification layer IS adding text. Every pass, every classification, every framework adds surface area for the LLM to attend to instead of the user message. If you're adding a pass to fix context problems, you're adding to the context problem.

## Case Study 5: Partial Snapshot Under-Querying (July 2026)

**Problem:** The 7-row Recent Actions block header said "format your reply like this" but didn't tell the model the block is PARTIAL. When the user asked "what's overdue?" with 22 open actions, the model answered from the 7-row snapshot and declared complete. 15 overdue items were silently dropped.

**Root cause:** The block heading gave formatting instructions ("• Action title — due date") but no completeness warning. The model followed instructions correctly — it formatted from what it had — but the instruction was incomplete.

**Fix:** Added to the block heading:
```
"This is a PARTIAL snapshot (capped at 7). When the user asks for completeness
('what's overdue?', 'list ALL pending', 'is there anything else?'), you MUST call
get_action_items to get the full list. Answer from this block ONLY for targeted
questions about specific items."
```

**Lesson:** Fix 1 traded "always has full context, wastes tool calls" for "usually has just-enough context, must know when to fetch more." That's the right trade, but it relocates the risk from over-querying (visible — you see the wasted steps) to under-querying (silent — you get an incomplete answer and don't know). The block header must explicitly tell the model the block is partial and when it must reach for a tool. The fix is NOT to enlarge the block (that just moves the cliff from 7 to 15); it's to make the model aware the block is a snapshot.

**Test:** Seed >7 items, ask "what's overdue?" → model must call `get_action_items`, not answer from block.

## Case Study 6: Thread Contamination Loop

**Problem:** Thread 80123f1c had 93+ messages of accumulated capability dumps. Each dump became thread history. Each new LLM call loaded the last 50 messages — all containing "Here's what I can do: Pipeline & CRM, Leads & Contacts..." — and produced another capability dump. Self-reinforcing. Deleting a few contaminated messages didn't help; the pattern was embedded across dozens of messages.

**Fix:** Thread 80123f1c archived → new thread 1a082b68. Fresh thread with zero history produced "Evening, Greg. How's the day treating you?" on first try.

**Lesson:** Thread history is a contamination vector. The LLM sees its own prior bad output and faithfully reproduces it. When a thread shows a pattern of wrong responses (capability dumps, spurious proposals), the fix is to archive the thread and start fresh, not to add more instructions to override the pattern. The instructions become MORE text that gets buried.

## Fix 3: Sidecar Inbox Durability (June 2026)

Applied to `/opt/ara/whatsapp-sidecar/index.js`. Replaced `pending.json` with `inbox_messages` SQLite table in `ara.db`.

**Pattern:**
1. On every inbound message, FIRST action (before any filtering) = `inboxWrite()` to SQLite
2. Process message normally (forward to ARA)
3. After 200 response = `inboxMarkProcessed(msgId)`
4. On startup = `inboxLoadUnprocessed()` → replay all with processed=false
5. Replaced backlog age check with `inboxIsProcessed()` — messages that arrive during reconnection are now processed instead of skipped

**Key insight:** `pending.json` only covers messages already accepted; messages arriving during the ~2-minute reconnection window are delivered by WhatsApp on reconnect but skipped as "backlog" (>15s old). The inbox cuts the age-based skip: if a message is in the inbox as unprocessed, it's processed regardless of age.

**Call sites:** voice notes, documents, text self-chat, chats.update — all 4 entry points moved to inbox-first.

## Fix 4: Confirmation Re-Anchoring Verification (June 2026)

**Verified in `/opt/ara/server.py`:** The confirmation short-circuit at lines 6336-6420 in `agent_chat()`:
1. `_live_pending_for_tenant()` → finds live pending action
2. `_classify_confirmation()` → "confirm"
3. Executes stored `pending_tool_calls` directly via `execute_tool()`
4. Returns with `return {"response": ...}` — does NOT fall through to observe loop

**Key insight:** When "yes please" re-lists all items instead of executing, it's because the confirm path was never reached — either `_classify_confirmation` returned "unrelated" (bad proposal description), or the pending action was auto-executed without creating a confirmation (intent = "now" instead of "ask"). The short-circuit itself works correctly; the failures are upstream in intent classification and proposal description.

**Residual observation:** After Fix 2 (deleting regex guards), commands auto-execute more freely because `_parse_execution_intent` defaults to "now" when no `[ACTION: ASK]` marker is present. Voice notes always force confirmation by design (`if voice_note and is_data_modifying: intent = "ask"`).

## Case Study 7: Within-Turn Read Cache (July 2026)

**Problem:** Testing Fix 1-4 together revealed that multi-step commands (e.g., "update Amardeep deadline to Friday and WhatsApp him") were taking 6 tools with duplicate reads — `get_action_items` called twice, `query_database` called twice, and `search_memory` called spursoriously. On a simple deadline update. Root cause: by step 4 of the observe loop, the result from step 1 has scrolled out of the LLM's attention window, so the model re-fetches the same data. This is Issue 4 (context loss in the loop) manifesting as redundant re-querying.

**Fix:** Implemented `_cached_execute()` wrapper in `/opt/ara/server.py`:

```python
def _cached_execute(tn, args, db, wa, tenant_id, _read_cache):
    """Execute a tool with within-turn read deduplication."""
    import json as _ce_json
    if get_tool_read_only(tn):
        key = f"{tn}:{_ce_json.dumps(args, sort_keys=True)}"
        if key in _read_cache:
            return _read_cache[key]
        result = execute_tool(tn, args, db, wa, tenant_id)
        _read_cache[key] = result
        return result
    return execute_tool(tn, args, db, wa, tenant_id)
```

`_read_cache` is initialized as `{}` at the start of `_run_observe_loop()`. All read-tool execution calls in the observe loop route through `_cached_execute`. The cache is keyed on `(tool_name, serialized_args)` and applies to read-only tools only.

**Result:** "Update Amardeep to Friday + WhatsApp" dropped from 6 tools (with 2 duplicates + spurious search_memory) to 5 tools (0 duplicates, 0 spurious calls, send_whatsapp actually called). Still 3 reads before write but tightly sequenced: get_action_items → get_lead_detail (phone for WhatsApp) → query_database → update_action → send_whatsapp.

**Safety rules:**
- Within-turn only — cache cleared between turns.
- Read-only tools only — writes bypass the cache unconditionally.
- Exact args match — `json.dumps(args, sort_keys=True)`.
- This is NOT a text-injection guard. It doesn't infer intent from prose. It prevents literal redundant work.
- Do NOT extend to cross-turn caching or write caching — data can change between turns.

## Implementation Reference: Tiered Context Injection (Fix 1)

Applied to `/opt/ara/server.py` in `agent_chat()`. Inserted before the pipeline injection block (line ~6691).

**Classification call (cheap, temperature 0, three-word output):**
```python
from induction_engine import call_llm as _tier_llm
_tier_prompt = """Classify this CRM user message into exactly one word:
smalltalk (greeting, thanks, chitchat)
status (question about existing state)
command (request to do/change something)
Message: """ + user_msg[:200] + """
Answer with EXACTLY one word: smalltalk, status, or command."""
_tier = _tier_llm([{"role": "user", "content": _tier_prompt}], temperature=0.0)
```

**Conditional injection:**
- `smalltalk` → no pipeline, no recent-actions. System prompt = identity + time only.
- `status` → recent-actions block only (`_build_recent_actions_block`). No lead/deal dump.
- `command` → full pipeline + recent-actions (current behavior).
- Default on error: `command` (fail toward more context, never less).

## Implementation Reference: Prose-After-Result (Fix 2)

Deleted from `/opt/ara/server.py`:
- `_claims_action_without_call()` function (4 regex families, 40 lines)
- Claim nudge injection (90-word correction appended to loop_messages)
- `_action_map` cross-check (12 verb→pattern mappings + fix prompt)
- `_analysis_mode` keyword sniffer (3 keyword sets)
- Analysis mode guard (blocks data-modifying tools)
- Mode reminder injection
- Legacy `_parse_tool_calls` fallback in observe loop
- `claim_nudge_fired` variable and all references

**Added to AGENT_SYSTEM_PROMPT_BASE (Tool-Calling Principles section):**
```
Never describe a write or action as completed unless the tool result confirms it.
Your prose must follow the tool result, not precede it.
If you haven't called the tool yet, do not say "Done" or "Updated" — say "I'll [action]" instead.
```

**Key insight:** The reason claim-without-call happens is that prose generation and tool invocation are decoupled surfaces. The fix closes the gap at the source (prose discipline) rather than detecting the disagreement after the fact (regex).

## Fix A: Per-Tier Actions Block + search_memory Narrowing (July 2026)

**Problem 1:** The recent-actions fact sheet was injected unconditionally (after the tier branches in `agent_chat()`). Smalltalk — which is supposed to get nothing beyond the base system prompt — was still receiving the full 7-action fact sheet. This half-reintroduced the salience problem Fix 1 was built to eliminate: "Hi Ava" had live action data to potentially parrot.

**Fix:** Moved `_build_recent_actions_block(db, tenant_id)` into the `status` and `command` branches only. The smalltalk branch now ends with the base system prompt and nothing else — no pipeline, no actions block, no context section beyond what base already contains.

**Problem 2:** The system prompt actively instructed "MEMORY CHECK: Before stating your plan, if the message references a person, company, or deal, call search_memory" — causing spurious `search_memory` calls on every command that touched a lead.

**Fix:** Narrowed to: "MEMORY: search_memory is available for looking up past session facts. Use it only when the user explicitly references a past conversation. Do NOT call it for routine commands like updates, sends, or status checks."

## Fix B: Intent-Based (Not Keyword-Based) Tier Classification (July 2026)

**Problem:** The tier classifier prompt defined each tier by example trigger words ("update", "send", "create"...). A command phrased without an imperative verb — "Rajesh's deadline should really be Friday", "I think Acme needs to move to qualified" — contained no trigger word and got mis-tiered as status. The model lacked full pipeline context and couldn't act cleanly. The mis-tier was silent: the user asked for a change and got a non-answer or incomplete context.

**Fix:** Rewrote the tier classifier prompt from keyword-based to INTENT-based. Each tier is defined by what the user WANTS, not by vocabulary:

```
smalltalk — Greeting, thanks, acknowledgment, or chitchat. No request and no question about the pipeline.
status — The user is asking about EXISTING state and wants only to be told something. Pure information request, no change implied.
command — The user wants something created, changed, sent, scheduled, or done. This includes indirect/declarative phrasing that implies a desired change even without an imperative verb. ("X should be Friday", "Acme needs to move to qualified", "let's get Rajesh a follow-up")
```

**Tie-break rule:** If it's ambiguous whether the user wants information or a change, classify as command. The asymmetry: a command mis-read as status fails to act (bad, user-visible); a status mis-read as command merely over-supplies context (cheap, harmless).

**Gate tests:**
- "Rajesh's deadline should really be Friday" → command (declarative, no imperative verb — the regression Fix B exists for)
- "I think Acme should move to qualified" → command
- "is Rajesh's reminder set for Friday?" → status (genuine question, proves bias didn't overcorrect)

**Key insight:** Keyword-based classification inevitably has blind spots — any imperative not in the trigger list is missed. Intent-based classification generalizes. The command-bias tie-break is deliberate: better to over-supply context to a status question than to starve a command. Safety defaults preserved: one-token output, temperature 0, fail-open to command on error.

**Residual risk:** "yes" to a pending confirmation classifies as smalltalk by the tier classifier. This is safe because the confirmation flow (_classify_confirmation) runs BEFORE the tier classifier — a "yes" to a live pending action never reaches the tier. But if the confirmation flow ever skips (pre_confirmed=True, or pending already pruned), "yes" would route as smalltalk with no pipeline context.

## Regression Battery (July 2026)

Full integration test suite verifying Fixes 1-4 + A + B hold together. Seven sections covering:
1. Context discipline (smalltalk gets nothing, status gets actions-only, command gets full pipeline)
2. Tier classification accuracy (6 test cases including declarative commands and overcorrection guard)
3. Action honesty (no false claims, write-read consistency, guard deletion audit, tools fire not described)
4. Observe-loop efficiency (no duplicate reads, multi-step chains, read-only cache, MAX_TOOL_STEPS=10)
5. Status-block completeness (>7 items → model queries beyond block, block cap stays at 7)
6. Confirmation integrity (specific action fires, stale pending pruned, rejection cancels, no spurious confirm classifier)
7. Cross-fix integration (full conversational arc: greeting → status → declarative command → confirm → self-poisoning check)

Key cross-fix tests: full conversational arc exercises Fixes 1, A, B, 4 together. Self-poisoning check after arc proves smalltalk resists history poisoning end-to-end. Latency sanity verifies confirm classifier only runs when a live pending exists.

### Case Study 9: Test Infrastructure — Journalctl Timing in Test Scripts

**Problem:** Python test scripts using `subprocess.run(["journalctl", "--since", "8s ago"])` frequently return empty output for tier classification checks. The 8s window is too tight — the log line arrives after the window closes.

**Fix:** Two approaches:
1. Increase sleep between `call()` and log capture to 3-4s, and widen `--since` to 15-20s
2. Better: skip log-based tier verification entirely. Verify tier classification by behavior — does the reply contain pipeline data (command), actions-only (status), or nothing (smalltalk)? The behavioral check is more reliable and tests the actual user-facing outcome.

**Applied in:** All regression battery test scripts (gates 1-4, final battery A-E). The 9 false negatives from tier log checks were all confirmed correct by server log verification.

### Case Study 10: Described-But-Uncalled Retry in Observe Loop (July 2026)

**Problem:** Even with Fix 2 (deleting regex guards) and the prose-after-result invariant, multi-step commands still produced described-but-uncalled writes. The model would call `get_action_items → update_action` for "update X and send Y" but describe the WhatsApp in prose ("Here's the WhatsApp I'll send...") without calling `send_whatsapp`.

**Root cause:** At line ~5834 in `_run_observe_loop()`, the empty-tool_calls branch did `final_text = text; break` unconditionally. Any text describing a write but lacking a tool call was treated as a terminal response. The model could say "Here's the WhatsApp I'll send" and the loop would accept it as done.

**Fix:** Replaced the unconditional break with four-case logic in `_run_observe_loop()`:

```python
if not tool_calls:
    # Case 1: text doesn't describe a write → genuine answer, break
    _describes_write = bool(re.search(write_verbs, text))
    if not _describes_write: break

    # Case 2: text asserts a write as done with no tool call → one retry
    # MUST run before proposal check: "Done. Updated. Shall I send?" should retry
    _asserts_done = bool(re.search(assertion_pattern, text))
    if _asserts_done and not retry_used:
        retry_used = True
        loop_messages.append({"role": "user", "content":
            "You described [verb] something but issued no tool call, so it did not happen. "
            "Either call the tool now, or phrase it as a question."})
        continue

    # Case 3: text is a proposal ("shall I", "want me to", ends with ?) → break
    _is_proposal = bool(re.search(proposal_pattern, text)) or text.endswith("?")
    if _is_proposal: break

    # Case 4: retry exhausted → downgrade to honest ("drafted, not sent")
    if retry_used:
        _downgraded = re.sub(r"(done|sent|updated)", "drafted", text)
        final_text = _downgraded + " (drafted, not sent — want me to?)"
        break
```

**Key design decisions:**

1. **Assertion check BEFORE proposal check** (case 2 before case 3). The initial implementation had the proposal check first, which caused "Done. Updated. Now for the WhatsApp — what do you want me to send him?" to break as a proposal (the question mark triggered case 3) instead of retrying (case 2 should have caught "Done. Updated." as an assertion). The reorder fixed this: "✅ Deadline updated... → Friday" triggers case 2 → retry nudge → model calls send_whatsapp on next turn.

2. **Proposal-vs-assertion distinction:** A confirmation-seeking proposal ("Shall I send?", "Want me to?") must NEVER trigger the retry — only an unhedged assertion of an uncalled write does. This prevents re-breaking the confirm flow.

3. **One retry maximum per turn** (`retry_used` flag). No unbounded nudging — this is the difference from the deleted `_claims_action_without_call`, which could loop.

4. **Retry nudge is short and appended once.** 30-40 words. It does not displace the original user message or prior context the way the old claim nudge did.

5. **Broadened assertion patterns:** Added "let me", "draft the", "now" to the assertion regex to catch indirect assertion language ("let me draft the WhatsApp", "here's the plan"). The initial narrower patterns missed these.

**Variable:** `retry_used = False` initialized at start of `_run_observe_loop()` alongside other loop-state variables.

**Result:** "update Amardeep's deadline to Friday and send him a WhatsApp" now produces both `update_action` AND `send_whatsapp` in the tool list. The first empty-tool_calls hit (text="✅ Deadline updated...") triggers case 2 → retry → model calls send_whatsapp → both actions complete.

**Gate test:** Send "update X to Friday and send him a WhatsApp" → assert both update_action AND send_whatsapp appear in tool_results.

**Residual note:** Single-action sends ("send Amardeep a WhatsApp") work without the retry — the model calls send_whatsapp directly. The retry only fires for multi-step commands where the model describes the second action in the same prose response as the first action's tool calls.
