# Eval Agent Prompt v3 (June 2026)

TA-approved + advisor-refined eval agent system prompt for post-call meeting transcription processing.

## Architecture

```
Voice note → Scribe v2 / Whisper → transcript
  → eval_meeting tool (or POST /api/eval/transcript)
  → LLM with this system prompt
  → structured JSON → lead gate → grouping → confirmation → commit
```

## Key Design Decisions

1. **Extract atomically, group mechanically** — the LLM extracts one action per commitment. The integration layer groups ava_send items by (recipient, channel, due_date).

2. **No item cap** — every commitment is captured. The integration layer's grouping keeps the rep's review manageable.

3. **Always-ask lead gate** — the rep MUST confirm the lead before anything is attached, even on unambiguous matches. This eliminates the "wrong lead" data corruption class.

4. **Notes confirmed, not auto-written** — the rep reviews and approves the note before it's written to the CRM.

5. **Owner routing** — `owner: "agent"` (auto-written to rep board) vs `owner: "ava_send"` (gated, requires_confirmation: true).

6. **Due firmness** — `"firm"` (explicit date) vs `"vague"` ("early next week" → null, surfaced to rep).

## Prompt Location

- `/opt/ara/eval_agent_prompt.py` — EVAL_AGENT_SYSTEM_PROMPT
- `/opt/ara/tests/test_eval_agent.py` — 6 prompt unit tests (all passing)

## Test Coverage

| Test | What it proves |
|------|---------------|
| clear_meeting_with_sends | ava_send items tagged, channel="email", firm dates, lead commitments in notes |
| agent_only_tasks | owner="agent", requires_confirmation=false, zero sends |
| vague_timing | due_firmness="vague", due_at=null |
| garbled_noise | confidence="low", zero actions, lead_summary=null |
| multiple_sends_same_recipient | extracted atomically, same recipient/channel |
| lead_commitment_not_action | client commitments → notes, rep commitments → agent actions |
