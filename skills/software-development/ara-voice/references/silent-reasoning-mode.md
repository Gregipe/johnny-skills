# Silent Reasoning Mode for Voice Agents

## Problem
Voice agents narrate every tool call via TTS ("Let me search for that lead... Found them... Let me check the pipeline..."). Each utterance costs TTS credits and adds 1-3s latency. Users hear procedural narration they don't care about.

## DeepSeek v4 Cannot Follow Long System Prompts (CRITICAL)
**The 20-line verbose prompt was completely ignored.** DeepSeek kept speaking every thought line. A 5-line punchy version fixed it:

```
SILENT REASONING - NEVER SPEAK WHILE DOING WORK
Call tools silently. Speak only the final result. Your thoughts go to the dashboard, not TTS.
If you are looking up a lead, searching, staging, or calculating - stay silent.
What you CAN say: batch confirmations, clarifying questions, final results, greetings.
That is it. Nothing else. Silence during work saves audio cost.
```

**Rule: Keep voice system prompt sections under 6 lines.** Attention-limited models skip verbose sections. Make each instruction punchy and position-critical words at the start ("NEVER SPEAK").

## Forbidden Speech Patterns (add to prompt)
- Transition phrases: "Got it," "Let me clarify..." "Let me also check..."
- Process narration: "Let me start by looking up..." "Let me now stage..."  
- Recaps: "You said no action on Vinay so we'll skip him."
- Self-congratulation: "Good, I found three leads."
- Counts: "I've identified three."

## Prompt-Only Silence vs Hard Gate
A `SilentReasoningGate` FrameProcessor was attempted but **removed** because it blocked `StartFrame` system frames, preventing pipeline initialization. Prompt-only silence is sufficient.

## Implementation Layers
1. **System prompt (5-6 lines)** - short, punchy, forbidden phrases listed
2. **Dashboard thinking feed** - RTVI event-driven, shows tool calls as spinner → checkmark
3. **Audio cue** - 180Hz sine wave at 3% during tool calls (Web Audio API)
