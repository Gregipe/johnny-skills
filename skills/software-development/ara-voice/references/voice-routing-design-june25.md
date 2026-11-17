# Voice Note Routing — Eval vs Coaching (June 2026)

TA-reviewed and conditionally approved. Built but awaiting server+sidecar restart to activate.

## Decision: A+C (Keyword + Ambiguity Fallback)

### Routing Logic
```
Voice note arrives → transcribed
    ↓
Does transcript contain "eval" or "evaluate"?
  (full transcript scan, not just first N words)
    → YES: EVAL PIPELINE (_process_eval_meeting)
    → NO:  Also check sidecar caption (bonus, if available)
            → YES: EVAL PIPELINE
            → NO:  Is duration > 90 seconds?
                    → YES: Ava ASKS "Is this a meeting to evaluate, or an action?"
                    → NO:  COACHING PIPELINE (existing behavior)
```

### Why transcript-first, not caption-first
- `audioMessage.caption` field is unverified in Baileys — may not exist
- Transcript matching catches spoken intent ("evaluate this call")
- Caption is bonus-only, not a dependency

### Keyword set
- "eval", "evaluate" — ONLY
- "meeting" REMOVED — false positives on "remind me about the meeting tomorrow"
- Case-insensitive, full transcript scan

### Ambiguity threshold
- 90 seconds — long enough to distinguish meeting recordings from voice commands
- Known risk: users who frequently send long voice memos will be asked repeatedly (Phase 2: preference learning)

### Implementation
- `server.py`: `_check_eval_keyword()`, `_process_eval_meeting()`, `_handle_ambiguity_ask()`
- Voice-inbound routing added after transcription, before coaching pipeline
- Sidecar: caption field in voice-note payload (bonus)

## TA Verdict: CONDITIONALLY_APPROVED
- Transcript-first approach (decoupled from unverified Baileys field)
- "meeting" keyword dropped
- Full transcript scan (not first 50 words)
- Ambiguity fatigue noted for Phase 2
