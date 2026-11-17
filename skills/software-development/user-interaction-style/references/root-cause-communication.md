# Root Cause Communication — When Things Break

When something goes wrong (especially production incidents with live leads), Greg wants the SINGLE root cause traced cleanly. He does NOT want:
- A list of 3+ simultaneous bugs that "cascaded" — that sounds like excuses
- Timezone explanations as the primary answer — they're implementation details, not the root cause
- "The fix caused another bug" narratives — that reveals the fix was wrong, not that the system is complex

He DOES want:
- What was the ONE thing that caused the cascade?
- Trace it from trigger → failure point → result. Clean causal chain.
- Example (good): "_check_silence_resume() ran every 30s because there was no rate limit. It matched a brand-new engaged lead with zero conversations. The IST bug made each follow-up fire instantly. 35× loop."
- Example (bad): "Three bugs combined: timezone mismatch, silent except block, and the silence engine had no throttle."

The good answer identifies the silence engine as the ROOT cause driving the 35 messages, with the timezone bug as the reason the looping guard failed. The bad answer lists 3 bugs as if they're co-equal, which reads as deflection.
