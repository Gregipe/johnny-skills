# Execution Intent Architecture

Replaces the old confirmation gate with a protocol-based approach where the LLM
declares execution intent via [ACTION:] markers and the code obeys.

## Design

### Protocol

The LLM appends one of two markers to its response:

- `[ACTION: NOW]` — Execute tool calls immediately
- `[ACTION: ASK]` — Wait for user confirmation

### System Prompt Instruction (added June 2026)

```
- **Execution intent protocol:** Every response with tool calls MUST include
  an execution intent marker:
  - **[ACTION: NOW]** — Execute tool calls immediately. Use when:
    * The user gave a direct command ("create a lead", "update email to...")
    * The user responded to your question with the information you requested
    * The user explicitly confirmed a previous proposal ("yes, do it", "go ahead")
    * A correction the user explicitly asked you to make
  - **[ACTION: ASK]** — Show the proposal and ask for confirmation. Use when:
    * You are proposing an action based on context or inference
    * Voice notes — STT garbles spellings, always show proposed values and ask
    * The action has significant side effects (sending messages, stage changes)
  - If no marker is present, **[ACTION: ASK]** is assumed for data-modifying tools.
  The marker goes on its own line at the END of your response.
```

### Data Structures

```python
# Module-level dict in agent_chat
_pending_actions: dict = {}  # key: (tenant_id, thread_id)
_PENDING_ACTIONS_TTL = 600   # 10 minutes

# Each entry:
{
    "response_original": str,  # Full LLM response with tool calls
    "tool_calls": [{"tool": str, "args": dict}],
    "response_clean": str,     # Clean text for display
    "timestamp": float,        # time.time()
}
```

### Parser

```python
def _parse_execution_intent(response):
    import re as _re
    m = _re.search(r"\[ACTION:\s*(NOW|ASK)\]", response, _re.IGNORECASE)
    if m:
        return m.group(1).lower()
    return None
```

### Decision Flow

```
User message → agent_chat
  |
  ├─ [CONFIRMED VOICE ACTION — EXECUTING] → ALWAYS execute (trusted internal marker)
  |
  ├─ Voice note (🎤) + data-modifying → ALWAYS ask (STT garbles names/emails/phones)
  |
  ├─ Pending action exists → check user intent:
  |    ├─ Confirmed (yes, ok, go ahead, send it) → execute stored tool calls
  |    ├─ Rejected (no, stop, wait) → clear pending, return clean response
  |    ├─ Details provided (name/company/email/phone + >20chars) → auto-confirm
  |    └─ Unknown → clear pending, treat as new
  |
  └─ No pending → check execution intent:
       ├─ [ACTION: NOW] → execute immediately
       ├─ [ACTION: ASK] → store in _pending_actions, return proposal
       └─ No marker → check if user provided requested details
            ├─ Yes → execute (responded to assistant's question)
            └─ No → read-only auto-executes, data-modifying → store as pending
```

## Regressions from Initial Deployment

Three regressions were introduced when the old confirmation gate was first
replaced with the new architecture. Each was caught by Greg testing with a
real voice note.

### Regression 1: Voice Note Create_Lead Skipped Confirmation

**What happened:** Greg voice-noted "Create a lead for Jimmie Tete at Bajaj..."
→ LLM generated `[ACTION: NOW]` → code executed immediately → lead was
created with STT-garbled spelling and no confirmation.

**Root cause:** The old voice note check only caught `update_lead` with
email/phone/name. The old code had the keyword gate as a safety net for
`create_lead` — when keyword check failed, it stored the proposal pending.
The new architecture removed the keyword gate, so `create_lead` with
`[ACTION: NOW]` slipped through.

**Fix (commit 47d8cd0):** Changed the voice note check from:
```python
elif user_msg.startswith('🎤') and any(
    t[0] == 'update_lead' and any(k in ('email', 'phone', 'name') for k in ...)
    for t in tool_calls
):
```
to:
```python
elif user_msg.startswith('🎤') and _is_data_modifying:
```

Now ALL voice notes with data-modifying tools require confirmation.

**Principle:** When removing a broader safety net (keyword gate), ensure any
remaining narrow checks are expanded to cover the same ground. The keyword
gate caught everything the LLM got wrong about intent. Without it, every
tool-level check must be comprehensive.

### Regression 2: SUGGEST_DEAL Follow-Up Missing

**What happened:** `create_lead` returned
`"✅ Created lead: Jimmie Tete (phone: ..., company: Bajaj) [SUGGEST_DEAL: ...]"`
Greg was never asked "Would you like me to create a deal for Bajaj?"

**Root cause:** The old code had a "Build follow-up message" section (~80 lines)
that parsed tool results for `[SUGGEST_DEAL:]` patterns and either re-called
the LLM with a deal-creation prompt or auto-generated the question. This section
was entirely removed when the new architecture replaced the confirmation gate.
The new code built the response from raw tool output but never checked for
deal suggestions.

**Fix (commit 47d8cd0):** Added SUGGEST_DEAL detection to the response builder.
After collecting action lines from execution results:

```python
_suggest_deal = ""
if any("[SUGGEST_DEAL:" in _r for _r in _results):
    import re as _srx
    for _r in _results:
        _sm = _srx.search(r"org=([^,]+)", _r)
        if _sm:
            _sug_org = _sm.group(1).strip()
            _suggest_deal = f"\\n\\n_{_sug_org}_ doesn't have a deal yet. Would you like me to create one?"
            break
response = (build_response) + _suggest_deal
```

**Principle:** Tool result patterns that trigger follow-up questions are NOT
cosmetic — they're part of the core product flow. Before removing post-execution
code, audit ALL tool return values for embedded directives like `[SUGGEST_DEAL:]`,
`[CANCEL:]`, `[WHATSAPP:]`, etc.

### Regression 3: Raw Tool Output Instead of Natural Language

**What happened:** Response was
`"✅ Jimmie Tete: Created lead: Jimmie Tete (phone: 0123456789, company: Bajaj)"`
instead of a natural language sentence.

**Root cause:** The old "Build follow-up message" section made a second LLM
call to synthesize a natural response from raw tool results. This was removed
in the new architecture. The new code built the response by joining tool output
strings directly.

**Fix (commit 47d8cd0):** Cleaned the raw output:
1. Strip `✅ Name:` prefix from tool results (whitespace-normalized regex)
2. Strip `[SUGGEST_DEAL:...]` from displayed text (append separately)
3. Skip entries starting with `Tool '` (raw debug prefix)
4. Join with ` | ` instead of raw concatenation

**Trade-off:** The response is shorter and more factual than the old
LLM-synthesized version. This is acceptable — Greg said the old verbose
responses were unnecessary. The key is that the information is all there.

## Verification Tests

The following test classes exist in `tests/test_enforcer.py`:

- `TestToolPendingStorage` — [PENDING] prefix stored in DB when tool not confirmed
- `TestAutoConfirmOnDetails` — Auto-confirm when user provides requested details
- `TestCreateLeadEnforcer` — Enforcer fires for create commands without tool calls
- `TestPhantomLookup` — Lookup-type hallucinations caught by new regex
- `TestPhantomWindowBug` — 30-char window edge case in phantom detection
- `TestNamingCorrectionOnProposal` — Correction to proposal does not fire enforcer

## Removed Code (~240 lines)

The following were removed from agent_chat in server.py:

1. **Keyword confirmation lists** — `_confirm_phrases`, `_reject_phrases`
2. **LLM intent detector** — The `CONFIRM/REJECT` secondary LLM call
3. **Voice note data dictation heuristics** — The `update_lead`-specific check
4. **"Build follow-up message" section** — The second LLM call on successful execution
5. **Direct execution else-branch** — The `else:` path for no-confirmation-needed tools
6. **Duplicated response-building code** — The confirmed vs unconfirmed paths

## Pitfalls

1. **Voice note check scoping**: The voice note check was originally scoped to
   `update_lead` because that was the only case where STT garbles mattered.
   But the keyword gate caught everything else. When the gate was removed, the
   scoping became a bug. Always check: "What was catching the cases this narrow
   check doesn't cover?"

2. **SUGGEST_DEAD is not cosmetic**: Tool return values with embedded directives
   are part of the product flow. Before removing any post-execution code, grep
   for ALL capital-bracket patterns in tool return strings.

3. **Response building without LLM synthesis**: Raw tool output is ugly.
   Always strip prefixes, normalize whitespace, and handle embedded directives
   before joining.

4. **[PENDING] prefix is critical**: Without it, the LLM sees unexecuted tool
   calls in the next turn's context and assumes they were executed. This was
   the root cause of the cascading hallucination bugs.

5. **Expired pending actions**: The `_PENDING_ACTIONS_TTL` cleans stale entries
   (10 min). Without cleanup, abandoned proposals accumulate in memory.
