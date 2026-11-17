# Voice TTS Markdown Problem

## Problem

ElevenLabs TTS reads raw text literally. Markdown formatting produces garbled output:

| LLM output | TTS pronounces |
|-----------|---------------|
| `**urgent**` | "asterisk asterisk urgent asterisk asterisk" |
| `*italic text*` | "asterisk italic text asterisk" |
| `🎯` | "target emoji" or garbled |
| `🔍` | "magnifying glass emoji" or garbled |

This makes voice responses sound robotic and confusing.

## The Fix is at the Prompt Level

The LLM controls what text TTS receives. Add to the system prompt:

```
NO MARKDOWN IN VOICE RESPONSES
When speaking, do NOT use markdown formatting. No **bold**, no *italic*, no emojis (use words instead).
Write in plain sentences that ElevenLabs TTS can pronounce naturally.
Use dashes or numbers instead of asterisks for lists.
```

**Do NOT try to fix this in the TTS layer** — stripping markdown from TTS output is a band-aid. The LLM should never produce markdown for voice in the first place.

## Why Not Strip at the Pipeline Level?

Stripping `**` markers between LLM output and TTS input seems cleaner but:
1. The LLM still produces markdown, wasting tokens
2. Emojis need a lookup table to convert to words ("🎯" → "target")
3. Some formatting has semantic meaning ("**urgent**" → should be spoken with emphasis, but the LLM would need to rewrite it)
4. The dashboard transcript would still show the raw markdown

The prompt-level fix is simpler, more reliable, and produces cleaner output at every layer.

## Related: Dashboard Rendering

The chat panel (dashboard.js line 4344) already converts `**text**` → `<strong>text</strong>`:

```javascript
div.innerHTML = text.replace(/\n/g, '<br>').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
```

But the voice transcript overlay (dashboard_template.py) uses `textContent`, not `innerHTML`, so markdown shows literally there too. The prompt-level fix covers both surfaces.
