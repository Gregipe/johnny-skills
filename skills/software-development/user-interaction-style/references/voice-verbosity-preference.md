# Voice Agent TTS Verbosity Preference

Greg gets VISIBLY frustrated when voice agents speak internal thinking via TTS.
Repeated 3+ times across sessions (July 2026) — a first-class frustration signal.

## Triggers (never speak these to TTS)

- "Let me check..." / "Let me look up..." / "Let me calculate..."
- "Got it, let me clarify..." / "I see the three actions..."
- Process narration: "Let me start by looking up these leads..."
- Restating what Greg just said before answering
- Date calculations: "Today is Friday, July 10th, 2026. From now to Monday..."
- Self-congratulation: "Good, I found three leads."

## Direct Quote

"This has every single bit of thinking that's being read out loud and it's
honestly very annoying."

## Rule

Voice agents MUST use structural pipeline filtering (NarrationGate
FrameProcessor), not prompt-based silence instructions. Prompt-only approaches
fail with DeepSeek and similar models. TTS costs real money per spoken
character — every narrated thought is wasted budget.

## Implementation

See `ara-voice-calling` skill → `references/narration-gate-processor.md` for
the Pipecat FrameProcessor implementation that strips narration before TTS.
