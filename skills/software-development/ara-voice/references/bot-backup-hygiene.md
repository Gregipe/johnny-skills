# Bot Backup Hygiene — Mandatory Pre-Patch Backup

**Rule:** Before any `write_file` or `patch` to bot.py (or voice_tools.py, dashboard_template.py), ALWAYS make a timestamped backup of the current LIVE file.

## The July 10 Disaster

bot.py was patched with brain dump mode. It broke basic STT. To roll back, I restored `bot.py.bak-phase2-pre` — a backup from July 4 that predated the Phase 2 system prompt rewrite. The live bot lost:

- Confirmation flow for write actions (voice_confirm instructions, explicit-keyword gate)
- Number pronunciation rules (mobile numbers as spaced digits, date formatting, IST as "I S T")
- Topic guard ("only discuss CRM/business/sales")
- Silent reasoning mode
- Date injection (`{today}` placeholder + datetime import)
- No-markdown rule for TTS
- Voice tool descriptions (50 tools: 18 read + 32 write)

Result: 30+ minutes of downtime while I rebuilt the prompt from scratch, referencing the context summary for what was lost.

## The Fix

```bash
# Before ANY patch:
cp /opt/ara-voice-agent/bot.py /opt/ara-voice-agent/bot.py.bak.$(date +%Y%m%d-%H%M%S)
```

Same for voice_tools.py and dashboard_template.py. The backup captures current state — not a weeks-old checkpoint.

## Recovery Pattern

If you do lose the prompt and need to rebuild:
1. Read the context summary for the original prompt content
2. Read the skill's `references/voice-system-prompt.md` for the prompt template
3. Rebuild section by section: personality → topic guard → formatting → pronunciation → confirmation flow → silent reasoning → date injection
4. Verify with `python3 -c "import py_compile; py_compile.compile('...', doraise=True)"`
5. Deploy, restart bot, verify `ss -tlnp | grep 7860` shows new pid
