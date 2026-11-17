# Confirmation Keyword Matching — Debugging History

## Bug Found 2026-06-05

The initial implementation used exact tuple membership:

```python
_confirm_keywords = ("yes", "send it", "confirm", ...)
if message.strip().lower() in _confirm_keywords:  # ❌
```

This failed when Greg replied **"Yes - go ahead"** — the string "yes - go ahead" is not in the tuple, so the message fell through to the normal coaching handler where Ava picked up Rajesh thread context.

## Fix

Regex prefix matching catches all natural variants:

```python
p = re.compile(r'^\s*(yes|yeah|yep|sure|send it|do it|go ahead|confirm|execute)[\s.!,-]*', re.I)
p.match("Yes - go ahead")  # ✅ match
p.match("yeah sure")       # ✅ match
p.match("send it")          # ✅ match
p.match("no")               # ❌ no match — good
```

## What Happened Without Match

Without the regex match:
1. Message went to `_handle_owner_coach_whatsapp` as normal coaching
2. Agent chat thread had context about Rajesh Sharma (from earlier auto-responses)
3. Ava misinterpreted "set a reminder" as sending a WhatsApp to Rajesh
4. The failed WhatsApp attempt was reported back instead of executing the Thomas George plan

**Key lesson:** Always test with realistic user input patterns. Greg's confirmation style includes combining keywords ("yes - go ahead"), not single-word replies.
