# Voice Handler Format Spec & Debugging Guide

## The Critical Contract

The write-tool handler in `voice_tools.py` MUST return the `pending_id` in a format
the LLM can reliably extract. The contract is:

```
STAGED pending_id=<uuid>
Description: <human-readable>
Read the Description back to the user VERBATIM.
Then ask them to say 'confirm' or 'cancel'.
When they say 'confirm', call voice_confirm(cancel=false, pending_id="<uuid>").
When they say cancel/no, call voice_confirm(cancel=true, pending_id="<uuid>").
Accept ONLY the word 'confirm' — not yes, okay, sure, or go ahead.
```

## Handler Implementation

```python
# In make_tool_handler(), the write-tool branch:
if data.get("ok"):
    desc = data.get("description", "I can do that for you.")
    pending_id = data.get("pending_id", "")
    result = (
        f"STAGED pending_id={pending_id}\n"
        f"Description: {desc}\n"
        f"Read the Description back to the user VERBATIM. "
        f"Then ask them to say 'confirm' or 'cancel'. "
        f"When they say 'confirm', call voice_confirm(cancel=false, pending_id=\"{pending_id}\"). "
        f"When they say cancel/no, call voice_confirm(cancel=true, pending_id=\"{pending_id}\"). "
        f"Accept ONLY the word 'confirm' — not yes, okay, sure, or go ahead."
    )
```

## Bug Pattern: Description-as-Pending-ID

**Symptom:** User stages a write, says "confirm," and Ava responds
"Looks like that action already went through!" or "There was a glitch."
The lead/deal/action is never created.

**Root cause:** The handler returned the OLD format:
```python
f"I've prepared this action: {desc} Say yes to confirm, or no to cancel."
```
The LLM extracted `desc` as the pending_id and called:
```
voice_confirm(pending_id="➕ Add lead: Moksh Malji — shall I create it?")
```
The server looked for an ActionItem with that text as ID → not found →
"pending action not found or already resolved."

**Verification:** Check `/var/log/ara-voice.log` for `voice_confirm` calls.
The `pending_id` argument MUST be a short hex UUID (e.g. `969923fb`).
If it's a description sentence, the handler is returning the old format.

## Bot Restart Is Mandatory

Patches to `voice_tools.py` on disk are invisible to the running Pipecat
process. After ANY handler change:
```bash
pkill -f "bot.py"
sleep 2
/opt/ara-voice-agent/.venv/bin/python /opt/ara-voice-agent/bot.py >> /var/log/ara-voice.log 2>&1 &
# Verify new pid: ss -tlnp | grep 7860
```
