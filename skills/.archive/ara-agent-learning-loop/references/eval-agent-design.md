# Post-Call Eval Agent Prompt

TA-aligned prompt for processing meeting/call transcriptions. Extracts summary, action items, lead notes, and quality signals.

## Location
`/opt/ara/eval_agent_prompt.py`

## Key Design Decisions (post-TA review)

| Issue | Before | After |
|-------|--------|-------|
| ISO 8601 | No timezone | `±HH:MM` offset, `T09:00` default, `+05:30` IST fallback |
| Summary | One ambiguous field | Split: `internal_summary` + `lead_summary` (client-facing, null-safe) |
| Confidence | None | `high/medium/low` — low gates human review before committing |
| Quality | None | 9 coaching flags (objection handling, discovery, close attempts) |
| Action items | Max 5, undefined truncation | Priority ranking: dated > undated, deal-progress > admin |

## Integration
```
POST /api/eval/transcript/{tenant_id}
  → Eval agent processes transcript
  → Creates: lead_note (internal_summary + notes)
  → Creates: action_items (if confidence ≥ medium)
  → Sends: lead_summary via specified channel (WhatsApp/email)
  → Saves: quality_flags for coaching review
```

Triggers: dashboard upload, voice note pipeline (auto after Whisper), Ava coaching ("eval this")
