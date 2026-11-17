# Eval Agent Prompt v3 — June 25, 2026

Three-iteration prompt development with internal TA + external advisor reviews.

## Architecture Decision: Hybrid Review Model
- Internal data (notes, rep action items) → auto-written after extraction
- Outbound to lead (recap, proposal, pricing) → hard-gated for rep confirmation
- Chosen over "full review" because Greg's language was "ask whether it should send" — gate is on sending, not everything

## v3 Prompt (Final — Advisor-Aligned)

The eval agent processes meeting/call transcriptions. Returns structured JSON with:

### Output Fields
- `internal_summary` — Brief (2-4 sentences), outcomes/decisions first
- `lead_summary` — Client-facing draft, second person, ALWAYS a draft, null if unclear
- `lead_name` — CLAIM, not fact — integration layer always asks rep
- `confidence` — high/medium/low. Low → everything gates for human review
- `action_items[]` — with owner routing, due firmness, recipient/channel tags
- `notes` — Objections, signals, decision-makers
- `next_steps` — 1-2 sentences
- `quality_flags[]` — 9 coaching signals (missed_objection, handled_objection_well, etc.)

### Key Rules
- **Owner routing:** `owner: "agent"` (rep's own task, auto-write) vs `owner: "ava_send"` (send to lead, gated). `requires_confirmation: true` for sends.
- **Due firmness:** `"firm"` (explicit date, auto-set due_at) vs `"vague"` (approximate, due_at=null, surfaced to rep)
- **NO item cap** — capture every genuine commitment. Integration layer groups by (recipient, channel, due_date)
- **Extract atomically** — one action per commitment, integration merges deterministically
- **Lead gate always-ask** — even on unambiguous matches, rep confirms before attachment
- **Note gate** — rep reviews proposed note before it's written
- **Edge cases:** garbled transcript → null summaries, empty arrays, no invented content

### Test Coverage: 6/6 Passed
- clear_meeting_with_sends ✅
- agent_only_tasks ✅
- vague_timing ✅
- garbled_noise ✅
- multiple_sends_same_recipient ✅
- lead_commitment_not_action ✅

### Location
- Prompt: `/opt/ara/eval_agent_prompt.py` (EVAL_AGENT_SYSTEM_PROMPT)
- Tests: `/opt/ara/tests/test_eval_agent.py` (6 test cases using DeepSeek direct calls)
- Tool: `eval_meeting` in server.py (available to Ava via dashboard chat)
