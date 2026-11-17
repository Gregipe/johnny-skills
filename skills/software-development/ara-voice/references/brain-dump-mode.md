# Brain Dump Mode — Voice

## Overview

A voice mode where the user rants/rambles about their day, and Ava listens silently, then organizes everything into structured actions and retrievals. Activated by trigger phrases.

## Trigger Phrases

User says any of: "brain dump," "rant," "think out loud," "share updates," "random chat about my day," "listen and organize," "just thinking out loud"

## System Prompt (for bot.py DASHBOARD_SYSTEM_PROMPT)

```
BRAIN DUMP MODE
When the user says they want to "brain dump", "rant", "think out loud", "share updates", "random chat about my day", or similar — switch to LISTEN mode:

1. LISTEN SILENTLY — do NOT respond to individual points.
2. The user may jump between topics in no particular order. That's fine.
3. Keep mental notes of everything. Do not interrupt.
4. The user signals done with "that's it," "I'm done," "okay that's all," "done," or a long pause.

5. Organize the actual content they shared. Be SHARP — only include what was discussed:

- Actions: For each actionable item found.
- Lookups: Things to search or verify (only if mentioned).
- Notes: Non-actionable observations (only if there are any).

SKIP section headers for categories with nothing in them. Do NOT write "Updates - None requested" or similar filler.

6. ONE SINGLE VOICE CONFIRMATION will cover all staged actions. When the user says "confirm", confirm ALL pending voice actions. If there are multiple, confirm them one by one — call voice_confirm for each pending_id.

DATE RULES — CRITICAL
Today is {today}. When the user says:
- "Monday" or "this Monday" → the NEXT Monday (not a past one)
- "next Wednesday" → the Wednesday AFTER the current week
- "mid next week" → Wednesday or Thursday of next week
- "tomorrow" → the next calendar day
- "next month" → first week of next month

ALWAYS calculate dates relative to TODAY. NEVER create actions with dates in the past.

NO MARKDOWN IN VOICE RESPONSES
When speaking, do NOT use markdown formatting. No **bold**, no *italic*, no emojis. Write in plain sentences. Use dashes or numbers instead of asterisks for lists.
```

## Date Injection

The `{today}` placeholder must be dynamically replaced at bot startup:

```python
from datetime import datetime

# In the bot() function, before building the pipeline:
today_str = datetime.now().strftime("%A, %B %d, %Y")
system_prompt = DASHBOARD_SYSTEM_PROMPT.format(today=today_str)
```

This produces: "Today is Saturday, July 12, 2026."

## Multi-Action Staging

When the brain dump produces multiple actions, the LLM stages them one at a time via `create_action` (write tool). Since the auto-cancel was removed from voice_stage, all actions coexist. The LLM must track each pending_id and confirm them all when the user says "confirm."

## Past Bugs

1. **Breakage via prompt bleed (July 10)** — Adding the full brain dump prompt to `DASHBOARD_SYSTEM_PROMPT` (the main prompt) broke basic STT. The "LISTEN SILENTLY — do NOT respond to individual points" instruction leaked into normal conversations, causing the LLM to stay completely silent for every voice session. **Fix:** Brain dump must be an opt-in mode, NOT baked into the default prompt. Keep it as a separate prompt string (`BRAIN_DUMP_PROMPT`) and switch to it only when the user explicitly triggers it. The lesson: broad behavioral instructions added to the default system prompt will affect EVERY interaction — gate them behind an explicit mode switch.

2. **Summary boilerplate** — original prompt produced "UPDATES - None requested yet" for every empty category. Fixed: "SKIP section headers for categories with nothing in them."

3. **Past-date actions** — "Monday" resolved to the previous Monday because LLM didn't know today's date. Fixed: date injection.

4. **Markdown in TTS** — `**bold**` and emojis mangled by ElevenLabs. Fixed: "NO MARKDOWN IN VOICE RESPONSES" rule.

5. **Single-action staging** — action 2 cancelled action 1. Fixed: auto-cancel removed from voice_stage, multiple pending actions coexist.
