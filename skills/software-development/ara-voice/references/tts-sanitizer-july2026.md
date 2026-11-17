# TTSSanitizer — Strip Markdown Before TTS (July 12, 2026)

## Purpose
ElevenLabs TTS can't pronounce markdown formatting (`**bold**`, `*italic*`), emojis, em-dashes, or heading markers. The TTSSanitizer sits between NarrationGate and TTS in the voice pipeline, stripping these before text reaches TTS.

## Pipeline Position
```
LLM → NarrationGate → TTSSanitizer → TTS
```

## What It Strips

| Character | Treatment |
|-----------|-----------|
| `**bold**` | → `bold` (keeps content, strips wrappers) |
| `*italic*` | → `italic` |
| `__underline__` | → `underline` |
| `~~strikethrough~~` | → `strikethrough` |
| `` `code` `` | → `code` |
| `—` (em-dash U+2014) | → `, ` (comma) |
| `–` (en-dash U+2013) | → `-` (hyphen) |
| `## heading` | → `heading` (strips # markers) |
| `* bullet` / `- bullet` | → `bullet` (strips list markers) |
| Emojis | → removed completely |

## Implementation

```python
class TTSSanitizer(FrameProcessor):
    """Sits between NarrationGate and TTS. Strips chars TTS can't pronounce."""

    _DASHES = str.maketrans({
        '\u2014': ', ',   # em-dash
        '\u2013': '-',    # en-dash
    })

    _MD_PATTERNS = [
        (re.compile(r'\*\*(.+?)\*\*'), r'\1'),   # **bold**
        (re.compile(r'\*(.+?)\*'),     r'\1'),   # *italic*
        (re.compile(r'__(.+?)__'),     r'\1'),   # __underline__
        (re.compile(r'~~(.+?)~~'),     r'\1'),   # ~~strikethrough~~
        (re.compile(r'`(.+?)`'),       r'\1'),   # `code`
    ]

    _EMOJI = re.compile(
        '[\U0001F600-\U0001F64F'
        '\U0001F300-\U0001F5FF'
        '\U0001F680-\U0001F6FF'
        '\U0001F1E0-\U0001F1FF'
        '\U00002702-\U000027B0'
        '\U000024C2-\U0001F251'
        '\U0001F900-\U0001F9FF'
        '\U0001FA00-\U0001FA6F'
        '\U0001FA70-\U0001FAFF'
        '\U00002600-\U000026FF'
        '\U0000FE00-\U0000FE0F'
        '\U0000200D'
        ']+', flags=re.UNICODE)

    def _sanitize(self, text: str) -> str:
        if not text:
            return text
        text = self._EMOJI.sub('', text)
        text = text.translate(self._DASHES)
        for pattern, replacement in self._MD_PATTERNS:
            text = pattern.sub(replacement, text)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[\*\-\u2022]\s+', '', text, flags=re.MULTILINE)
        return text.strip()

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TextFrame) and hasattr(frame, 'text'):
            original = frame.text
            frame.text = self._sanitize(frame.text)
            if original != frame.text:
                logger.debug(f"Sanitized: [{original[:80]}] -> [{frame.text[:80]}]")
        await self.push_frame(frame, direction)
```

## Critical Bug — `\u0001` Control Character (July 12, 2026)

**Symptom:** Voice mode started, received instruction, replied with "inference engine fired" but TTS didn't work and listening mode shut down. When TTS did produce audio, it read half-lines and garbled content.

**Root cause:** The markdown regex patterns used `r'\u0001'` (unicode control character SOH) as the replacement string instead of `r'\1'` (regex backreference to captured group). Every `**bold text**` was replaced with a literal control character instead of `bold text`:

```python
# BROKEN — replaces content with control character
(re.compile(r'\*\*(.+?)\*\*'), r'\u0001'),   # **Start discussion** → \x01

# FIXED — keeps captured content
(re.compile(r'\*\*(.+?)\*\*'), r'\1'),        # **Start discussion** → Start discussion
```

**Second crash:** After the `\u0001` fix, a second crash occurred: `name '_re' is not defined` in `_sanitize()`. The method used `_re.sub()` but `_re` was only imported in a build script, not at module level in bot.py. Fixed by using the already-imported `re` module.

**Impact:** The control character replacement corrupted ALL text that contained markdown formatting — which is most LLM responses. TTS produced nonsense audio or crashed the pipeline. Combined with `function_call_report_level="FULL"` sending corrupted events to the client, the entire voice session collapsed.

## Design Principle
The system prompt already tells the LLM "Never use **, *, or emojis. Write everything as plain spoken sentences." But the sanitizer is belt-and-suspenders — LLMs don't always comply. Never rely on prompt instructions alone for TTS input quality.
