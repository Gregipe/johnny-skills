# Voice Write Confirmation — Debugging Session (July 2026)

## The Bug

User says "confirm" after staging a lead, but Ava says "action already resolved" or "glitch." Lead never gets created. Voice write confirmation appears broken end-to-end.

## Root Cause (two-layer)

### Layer 1: Bot running stale code

The `voice_confirm` FunctionSchema was registered in `voice_tools.py` on disk, but the bot process (started hours earlier) loaded the OLD version at startup. The tool simply didn't exist in the running process.

**Detection:** `grep -c "voice_confirm.*FunctionSchema" voice_tools.py` showed the tool was in the code, but the running process PID was from before the file modification time.

**Fix:** `pkill -f "bot.py"` then restart. Verify `ps -p <new_pid> -o lstart=` is AFTER `ls -l voice_tools.py`.

### Layer 2: Write handler returning description as pending_id

Even after the bot loaded the new code, the write tool handler returned:
```
"I've prepared this action: ➕ Add lead: Moksh Malji (HDFC Bank) — shall I create it?"
```

The LLM passed the description TEXT as `pending_id` to `voice_confirm`:
```
voice_confirm called with: pending_id = "➕ Add lead: Moksh Malji (HDFC Bank) — shall I create it?"
```

The server looked for an ActionItem with that string as ID → not found → "pending action not found or already resolved."

**Detection:** Log search:
```
grep "voice_confirm.*pending_id" /var/log/ara-voice.log
```
If pending_id values are long sentences instead of UUIDs (8-char hex), the handler isn't returning the real ID.

**Fix:** The write handler must return the actual UUID from the server response:
```python
if data.get("ok"):
    pending_id = data.get("pending_id", "")
    result = (
        f"STAGED pending_id={pending_id}\n"
        f"Description: {desc}\n"
        ...
    )
```

The LLM then extracts `pending_id=93b6d059` and passes `"93b6d059"` to `voice_confirm`.

## Diagnostic Timeline

This was a 3-phase debugging effort:

| Phase | What was tried | What was actually wrong |
|-------|---------------|----------------------|
| 1 | Server endpoints tested via curl — all passed | Server was fine, bot had old code |
| 2 | voice_confirm FunctionSchema registered (was dead code) | Registered but bot process NEVER RESTARTED |
| 3 | Bot restarted, still broken | Write handler still returning description, not UUID |

## Key Log Signatures

**Working (correct):**
```
OpenAILLMService#1 Calling function [voice_confirm] with arguments {'cancel': False, 'pending_id': '93b6d059'}
```

**Broken (description as pending_id):**
```
OpenAILLMService#1 Calling function [voice_confirm] with arguments {'cancel': False, 'pending_id': '➕ Add lead: Moksh Malji (HDFC Bank) — shall I create it?'}
```

**Missing tool (old code in memory):**
- No `voice_confirm` call in logs at all
- LLM says "action already resolved" without calling any tool
- LLM re-calls `create_lead` in a loop

## Prevention Checklist

After ANY change to `voice_tools.py`:
1. Kill the old bot: `pkill -f "bot.py"`
2. Start fresh: `python bot.py >> /var/log/ara-voice.log 2>&1 &`
3. Verify PID start time > file modification time
4. Test end-to-end: stage → confirm → lead in DB
5. Check logs for UUID-based pending_id in voice_confirm calls
