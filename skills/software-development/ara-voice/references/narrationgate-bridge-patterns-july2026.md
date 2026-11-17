# NarrationGate Extended Bridge Patterns (July 12, 2026)

## Problem
The original NarrationGate only pattern-matched explicit narration prefixes ("Let me check", "I'll look"). Multi-sentence thinking that included factual context ("Today is Sunday, July 12, 2026", "Two days from now is Tuesday") leaked through to TTS because these don't match narration patterns.

Additionally, the state machine prematurely exited suppression mode after a sentence boundary — once a narration sentence ended with a period, the next sentence was treated as a response even if it was still internal thinking.

## Fix — Proper State Machine
Rewrote the NarrationGate with a clean 6-state machine:

- INIT → EVALUATING → SUPPRESSING | PASSING
- SUPPRESSING → TOOL_WINDOW → BRIDGE_FILTER → PASSING

**Key improvement:** When narration is detected, the state machine enters SUPPRESSING and stays there even across sentence boundaries. It only exits when it encounters text that is clearly NOT narration, NOT bridge, and NOT contextual filler.

## Extended Bridge Patterns
Added patterns that catch contextual thinking masquerading as facts:

```python
BRIDGE_PATTERNS = [
    r"^(here'?s? (what|the|your|is)|here you go|here we go)",
    r"^(alright|okay|right|so)[,!\\.]?\\s*(here'?s?|this is|I'?ve|we'?ve|the|your|it looks)",
    r"^(so|and)[,!\\.]?\\s*(here|this|that|it|I'?ve|we'?ve|the|your)",
    r"^(based on|according to|from what|looking at|after (checking|looking|reviewing))",
    r"^(I (can|found|see|have|got)|we (have|found|can))",
    r"^(it (looks|appears|seems)|there (are|is|were|was))",
    r"^today is ",           # NEW: "Today is Sunday, July 12, 2026"
    r"^currently ",          # NEW: "Currently showing 5 items"
    r"^right now ",          # NEW: "Right now there are"
    r"^from the (list|data|database|system)",  # NEW
    r"^the (current|only|first|second|third) ",  # NEW
    r"^that'?s? (the|all|it|what)",  # NEW
    r"^two days from now is ",  # NEW: "Two days from now is Tuesday"
    r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday),? ",  # NEW
]
```

## Answer-First Format (System Prompt)
Added to the voice agent system prompt to prevent listing-then-summarizing:

```
ANSWER-FIRST FORMAT
When the user asks "how many" or "what is" or "list" questions:
- START with the answer, then provide details.
- "You have 5 actions due tomorrow. They are: 1. ... 2. ... 3. ..."
- NEVER list items first then say the count at the end.
- If the user might be busy, give them the number first so they can interrupt.
```

## Voice Agent Audio Fix
- `function_call_report_level="NONE"` - suppresses tool call notification sounds and "undefined" popups
- `audio_out_auto_silence=False` - reduces background static during tool-call silence
