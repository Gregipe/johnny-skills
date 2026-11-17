# Email Signature Pattern for Cold Sequences

When building email channel prompts for AI SDR outbound sequences, the signature format should adapt based on conversation position:

## Rule

- **First email in a thread:** Sign with full name, title, and company
  - e.g. *"Ava — Business Lead, Hunar.ai"*
- **Follow-up replies (2nd+ email in same thread):** Sign with just first name
  - e.g. *"Ava"*

## Rationale
- First email establishes authority and context
- Subsequent emails assume the recipient already knows who you are
- Reduces friction — full signatures in reply chains look spammy

## Implementation

In the channel prompt `body` section, add:

```
## Signature
First email in a thread: sign with full name, title, and company
  — e.g. "Ava — Business Lead, Hunar.ai"
Follow-up replies in the same thread: just your first name
  — "Ava"
```

## How the LLM distinguishes first vs reply
The LLM needs context about whether it's the first email or a follow-up. This is usually handled by:
1. The system prompt telling Ava what sequence position she's in
2. The cadence configuration defining which step is being executed
3. The lead's engagement state (first_reply vs follow_up vs repeat_contact)

For cadence-generated emails (not live replies), each step in the cadence is treated as a separate "first email" since the lead hasn't replied yet.
