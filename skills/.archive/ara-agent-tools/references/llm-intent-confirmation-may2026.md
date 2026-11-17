# LLM-Based Intent Detection for Confirmation Gate (May 2026)

## Motivation

The original confirmation gate used a hardcoded `CONFIRMATION_WORDS` set with
`startswith()` matching. This was brittle:
- Failed on non-English confirmations: "kar de", "haan", "ho jaye" (Hindi/Hinglish)
- Required manual maintenance to add every possible confirmation variant
- Didn't understand context or tone (sarcasm, hesitation, shorthand)

## Architecture

```
User Message
     │
     ├── Direct command verb? → Execute immediately (no LLM check)
     │
     └── Not a direct command → Call LLM for intent detection
              │
              ├── "CONFIRM" → Execute tools, re-call LLM to synthesize
              │
              └── "REJECT" → Return clean response (don't execute)
```

## Implementation

### The Confirmation LLM Call

The server calls back to the same LLM that runs Ava, but with a minimal
system prompt focused only on confirmation intent detection:

```python
def _check_llm_confirmation(user_msg, llm_response_text):
    """Use LLM to determine if user is confirming or rejecting."""
    confirmation_prompt = (
        "Determine if the user is confirming or rejecting a proposed action. "
        "Understand tone, slang, shorthand, Hinglish, Hindi, and any language. "
        "Respond with exactly one word: CONFIRM or REJECT."
    )
    confirmation_msgs = [
        {"role": "system", "content": confirmation_prompt},
        {"role": "user", "content": (
            f"Ava proposed the following action to Greg:\n"
            f"---\n{llm_response_text}\n---\n\n"
            f"Greg replied: '{user_msg}'\n\n"
            f"Is Greg confirming or rejecting this action? "
            f"Respond: CONFIRM or REJECT"
        )}
    ]
    try:
        result = call_llm(confirmation_msgs)
        return "CONFIRM" in result
    except Exception:
        # Fallback: check keyword list
        return _check_keyword_confirmation(user_msg)
```

### Integration Point in agent_chat()

The confirmation check sits between parsing tools and executing them:

```python
# Parsed tool_calls from LLM response
tool_names = {t[0] for t in tool_calls}
needs_confirmation = bool(tool_names & data_modifying_tools)

# Step 1: Pre-check for direct commands (fast path, no LLM)
msg_lower = user_msg.lower().strip()
command_verbs = {"stop", "cancel", "send", "start", "trigger", "restart",
                 "pause", "resume", "create", "update", "delete", "remove",
                 "add", "schedule", "mark"}
first_word = msg_lower.split()[0] if msg_lower.split() else ""
is_direct_command = first_word in command_verbs

# Step 2: LLM-based intent detection (if needed)
if needs_confirmation and not is_direct_command:
    is_confirmed = _check_llm_confirmation(user_msg, llm_response_text)
else:
    is_confirmed = is_direct_command

# Step 3: Execute or defer
if needs_confirmation and not is_confirmed:
    # Show "Shall I proceed?" to the user
    ...
else:
    # Execute tools and re-call LLM
    ...
```

## What Gets Passed to the LLM

The confirmation LLM sees:
1. **System prompt**: "Determine if the user is confirming or rejecting..."
2. **User message**: Contains both Ava's proposal AND Greg's reply

This is critical — the LLM needs context to understand what "ye" or "kar de"
refers to. Without the proposal context, the LLM can't determine intent.

## What Direct Commands Bypass

Messages starting with known imperative verbs bypass the LLM check entirely:

| Verb | Example |
|------|---------|
| send | "send a message to Gregory" |
| create | "create a new lead" |
| stop | "stop all outbound" |
| cancel | "cancel pending actions for Gregory" |
| update | "update Gregory to qualified" |
| start | "start the cadence" |
| trigger | "trigger a follow-up" |
| schedule | "schedule a reminder" |
| mark | "mark as qualified" |
| delete/remove | "delete that action" |

Any message starting with one of these = implicit confirmation.

## Fallback Chain

1. **Direct command verb** → Execute (no LLM call)
2. **LLM intent detection** → CONFIRM or REJECT
3. **Keyword fallback** → If LLM call fails, check `CONFIRMATION_WORDS` set
4. **Default** → If all checks fail, reject (return "Shall I proceed?")

## Testing Checklist

After implementing, test these scenarios end-to-end:

| Message | Expected | Notes |
|---------|----------|-------|
| "yes" | CONFIRM | Basic English |
| "ye" | CONFIRM | Shorthand |
| "kar de" | CONFIRM | Hindi imperative |
| "haan" | CONFIRM | Hindi yes |
| "ho jaye" | CONFIRM | Hindi "let it happen" |
| "do it" | CONFIRM | English imperative (not in verb list) |
| "no" | REJECT | Clear rejection |
| "nahi" | REJECT | Hindi no |
| "ruk ja" | REJECT | Hindi "stop" |
| "send a test" | CONFIRM | Direct command verb |
| "create a lead for test" | CONFIRM | Direct command verb |
| "what else can you do?" | REJECT | Question, not confirmation |
| "ok" | CONFIRM | Casual assent |

## Known Limitations

- **Extra LLM call on every non-direct-command action** — Each confirmation
  costs one LLM API call. For high-volume scenarios, the keyword fallback is
  cheaper but less accurate.
- **LLM output parsing is fuzzy** — Uses `"CONFIRM" in result` substring check.
  Some models may output "I CONFIRM" or "CONFIRMATION" instead of "CONFIRM".
  Test with your specific model provider.
- **Context window consumed** — The confirmation call includes the full proposal
  text, which can be large for complex multi-tool proposals.
