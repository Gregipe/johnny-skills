# NarrationGate FrameProcessor — Strip LLM Thinking Before TTS

## Problem

LLMs (especially DeepSeek) ignore prompt instructions to stay silent during
tool calls. They speak narration like "Got it, let me check...", "Let me
calculate: from Friday to Monday...", "I see the three actions..." directly
to TTS. This wastes TTS credits and annoys users.

**Prompt-only approaches fail** — the LLM's default conversational behavior
overrides any "SILENT REASONING" instruction, regardless of how it's phrased.

## Solution: NarrationGate FrameProcessor

A Pipecat `FrameProcessor` that sits between LLM and TTS in the pipeline:

```
transport.input() → STT → user_aggregator → LLM → NarrationGate() → TTS → output
```

Uses Pipecat's built-in `TextFrame.skip_tts` field — TTS services already
check this flag and skip synthesis when `True`. No frame blocking needed.

### v2 Fix: Buffering + Standalone Patterns (July 2026)

The v1 approach had two fatal bugs:

**Bug 1 — Premature response mode:** LLM output streams in small chunks.
"Got" arrives first → doesn't match any pattern → classified as "response" →
response mode ON → all subsequent chunks pass to TTS. Fix: buffer 20 chars
before deciding.

**Bug 2 — Missing standalone patterns:** Patterns required specific
continuations like `got it, let me...` — but the LLM says "Got it. The action
is due..." (period, different subject). Fix: add standalone acknowledgment
patterns.

### Narration patterns (27 total):

```python
NARRATION_PATTERNS = [
    r"let me (check|look|see|verify|find|search|get|pull|grab|fetch|review|calculate|compute|figure|work out|think)",
    r"got it[,!]?\s*(let me|i'\s*ll|i will|let's|so|checking|looking)",
    r"i'\s*ll (check|look|search|find|get|pull|verify|calculate|review|fetch|sort)",
    r"i will (check|look|search|find|get|pull|verify|calculate|review|fetch|sort)",
    r"i'\s*m (checking|looking|searching|calculating|fetching|pulling|reviewing|thinking)",
    r"i am (checking|looking|searching|calculating|fetching|pulling|reviewing|thinking)",
    r"checking (that|this|on|the|for|now)",
    r"looking (that|this|up|at|into|for)",
    r"sure[,!]?\s*(let me|i'\s*ll|i will|one moment|just)",
    r"of course[,!]?\s*(let me|i'\s*ll|i will|one moment|just)",
    r"one (moment|second|sec)[,!]?\s*(let me|i'\s*ll|i will|while)",
    r"just (a (moment|second|sec)|checking|looking|let me)",
    r"alright[,!]?\s*(let me|i'\s*ll|i will|so|checking|looking)",
    r"okay[,!]?\s*(let me|i'\s*ll|i will|so|checking|looking)",
    r"so you (want|need|are|said|mentioned|asked)",
    r"calculating (that|now|for you|the|this|your)",
    r"let me calculate",
    r"let me (count|add|subtract|multiply|divide|tally|sum)",
    r"from (friday|monday|tuesday|wednesday|thursday|saturday|sunday) to",
    r"that'\s*s (a good|great|interesting) question",
    r"i see[,!]?\s*(let me|so|i'\s*ll)",
    r"understood[,!]?\s*(let me|i'\s*ll|i will)",
    r"right[,!]?\s*(let me|i'\s*ll|i will|so|checking)",
    r"let me clarify",
    r"let me (break|split|group|organize|sort|arrange)",
    r"i need to (check|look|search|find|get|pull|verify|calculate)",
    r"give me (a (moment|second|sec)|one (moment|second))",
]

# v2 ADDITION: Standalone acknowledgment patterns (no continuation required)
STANDALONE_NARRATION = [
    r"^(got it|understood|noted|roger|copy that|cool|nice|awesome|perfect|excellent)\.",
    r"^(got it|okay|alright|right|great|sure|ah|oh|hmm|huh|um|uh|well)",
    r"^(yes|yeah|yep|no|nope)[,!\.]?\s*(that'?s? (right|correct|fine|good|not|exactly))?",
]
```

### Critical constraint: Never block system frames

```python
async def process_frame(self, frame, direction):
    await super().process_frame(frame, direction)  # ALWAYS first

    if isinstance(frame, LLMFullResponseStartFrame):
        self._buffering = True
        ...
    elif isinstance(frame, LLMFullResponseEndFrame):
        self._buffering = False
        ...
    elif isinstance(frame, TextFrame) and self._buffering:
        # Buffer 20+ chars before deciding narration vs response
        self._accumulator += frame.text
        if len(self._accumulator) < 20 and not self._has_sentence_boundary(self._accumulator):
            frame.skip_tts = True  # buffer silently
            await self.push_frame(frame, direction)
            return
        # Now decide...
        if self._is_narration(self._accumulator):
            frame.skip_tts = True  # dashboard gets text, TTS skips
        ...
    else:
        # ALL other frames pass through unchanged
        await self.push_frame(frame, direction)
```

### Edge case: Full response is narration only

If the LLM output was entirely narration (e.g., "Let me check that for you."
followed by a tool call with no response text), `LLMFullResponseEndFrame`
arrives with `_narration_detected=True` and `_response_started=False`. TTS
is skipped entirely — no audio output. Narration text still reaches the
dashboard via forwarded frames.

## Verification

After deploying, check the voice log:
```bash
grep "NarrationGate" /var/log/ara-voice.log
```

Expected: `NarrationGate: NARRATION (skipping TTS): [...]` for filtered
text, `NarrationGate: RESPONSE (passing to TTS): [...]` for actual responses.

## History

- **v1 (July 10)**: Initial implementation with pattern matching. Broken: no
  buffering, strict continuation requirements.
- **v2 (July 10)**: Added 20-char buffer, standalone patterns, edge-case
  handling for full-narration responses.
- **v3 (July 12)**: Rewritten as proper state machine. v2 had a critical bug:
  when narration was detected AND a sentence boundary was reached, it set
  `_response_started = True` immediately. The next sentence (e.g., "Today is
  Sunday, July 12, 2026.") didn't match any narration pattern → passed to TTS.
  v3 fixes this with explicit states and bridge-phrase filtering after tools.

## v3: State Machine Architecture

The v2 approach was fundamentally flawed: it treated narration detection as a
binary decision per sentence. Real LLM output is multi-sentence: "Let me check
what's due. Today is Sunday. From the list, the only action is..." — the first
sentence is narration, but subsequent context-setting sentences don't match
narration patterns and leaked to TTS.

v3 replaces boolean flags with a 6-state machine:

```
INIT → EVALUATING → SUPPRESSING → TOOL_WINDOW → BRIDGE_FILTER → PASSING
```

| State | Meaning | TTS Behavior |
|-------|---------|-------------|
| `INIT` | Accumulating first ~20 chars | Suppress all |
| `EVALUATING` | Have enough text to decide | Depends on match |
| `SUPPRESSING` | Narration detected | Suppress ALL text |
| `TOOL_WINDOW` | Function calls in progress | Suppress ALL text |
| `BRIDGE_FILTER` | Tools done, filtering bridge | Suppress bridge, pass content |
| `PASSING` | Actual response content | Pass to TTS |

### State Transitions

- `INIT` → `EVALUATING`: 20 chars or sentence boundary reached
- `EVALUATING` → `SUPPRESSING`: text matches narration pattern
- `EVALUATING` → `PASSING`: text does NOT match narration
- `SUPPRESSING` → `TOOL_WINDOW`: `FunctionCallInProgressFrame` seen
- `SUPPRESSING` → `PASSING`: sentence boundary reached AND post-boundary text is non-narration, non-bridge
- `TOOL_WINDOW` → `BRIDGE_FILTER`: `FunctionCallResultFrame` seen
- `BRIDGE_FILTER` → `PASSING`: text is non-bridge, non-narration
- Any state → `INIT`: `LLMFullResponseStartFrame`
- Any state → `INIT`: `LLMFullResponseEndFrame`

### Critical Design Rule: NEVER exit SUPPRESSING on sentence boundary alone

The v2 bug: `_has_sentence_boundary` → `_response_started = True` → next
sentence leaks to TTS. The correct behavior: when a sentence boundary is
reached in SUPPRESSING state, split the accumulator at the boundary, reset
the accumulator to the post-boundary text, and re-evaluate. Only transition
to PASSING if the post-boundary text is genuinely non-narration AND non-bridge.

### Bridge Patterns (v3 addition)

After tools complete, the LLM generates bridge phrases before the actual
response. These must also be suppressed:

```python
BRIDGE_PATTERNS = [
    r"^(here'?s? (what|the|your|is)|here you go|here we go)",
    r"^(alright|okay|right|so)[,!\\.]?\\s*(here'?s?|this is|I'?ve|we'?ve|the|your|it looks)",
    r"^(so|and)[,!\\.]?\\s*(here|this|that|it|I'?ve|we'?ve|the|your)",
    r"^(based on|according to|from what|looking at|after (checking|looking|reviewing))",
    r"^(I (can|found|see|have|got)|we (have|found|can))",
    r"^(it (looks|appears|seems)|there (are|is|were|was))",
    r"^today is ",
    r"^currently ",
    r"^right now ",
    r"^from the (list|data|database|system)",
    r"^the (current|only|first|second|third) ",
    r"^that'?s? (the|all|it|what)",
    r"^two days from now is ",
    r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday),? ",
]
```

Context-setting phrases like "Today is Sunday, July 12, 2026" and "Two days
from now is Tuesday, July 14" are bridge phrases — the LLM is thinking out
loud about date calculations. They must be suppressed from TTS.

### Tool Window Detection

The gate detects tool-call activity via two Pipecat frames:

- `FunctionCallInProgressFrame`: emitted when the LLM starts calling functions
- `FunctionCallResultFrame`: emitted when each tool result arrives

`FunctionCallInProgressFrame` → enter `TOOL_WINDOW` (suppress all text).
`FunctionCallResultFrame` → enter `BRIDGE_FILTER` (filter bridge, then pass).

Note: `function_call_report_level="NONE"` in `TransportParams` does NOT prevent
these frames from flowing through the pipeline — it only controls RTVI client
messages. The NarrationGate still sees them.
