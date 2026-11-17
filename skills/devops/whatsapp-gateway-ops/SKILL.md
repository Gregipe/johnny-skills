---
name: whatsapp-gateway-ops
description: "Use when sending WhatsApp messages or transcribing voice notes."
version: 1.0.0
author: Johnny
license: MIT
metadata:
  hermes:
    tags: [whatsapp, gateway, bridge, outbound, johnny]
    category: devops
---

# WhatsApp Gateway Ops (Greg's self-chat bridge)

## When to Use

- Greg asks to send a WhatsApp message to an external contact (cab vendor, hotel, anyone) from
  his own number
- Verifying or troubleshooting the Baileys bridge (send failures, session, port discovery)

## Architecture

- The WhatsApp platform is a Baileys bridge linked to Greg's OWN WhatsApp account, running in
  `--mode self-chat`: inbound = Greg's "Message Yourself" thread only.
- Find the live process and its port: `ps aux | grep bridge.js` — shows `--port` (default 3000)
  and `--session` (profile-scoped, e.g. ~/.hermes/profiles/johnny/whatsapp/session).
- REST API on localhost:<port>: POST `/send` {chatId, message, replyTo?, mentions?},
  `/send-media` {chatId, filePath, mediaType?}, `/edit`, `/typing`, `/read`.

## Sending to an external contact

1. Confirm with Greg first — external outbound is approval-gated, every time (same rule as email).
2. Build the JID: country code + number + `@s.whatsapp.net` (e.g. 917478493874@s.whatsapp.net).
3. Write the message JSON to a scratch file, then POST:
   `curl -s -m 45 -X POST http://localhost:<port>/send -H 'Content-Type: application/json' -d @file.json`
4. VERIFY the response: `{"success":true,"messageId":"3EB..."}` — a real WhatsApp message id
   means the socket accepted it. Report to Greg with the id; never claim sent on HTTP 200 alone.
5. Tell Greg the vendor's reply lands on HIS phone, not in this chat — self-chat mode drops
   inbound stranger DMs by design, so replies never reach the agent.

## Pitfalls

- Sends come from Greg's own number with his identity — never send anything he didn't approve in
  writing, and keep the message factual (dates, prices, asks), not commitments.
- If /send returns an error ("not a contact" class), the number likely isn't on WhatsApp — fall
  back to giving Greg the number to call, or the vendor's website form. Don't retry-loop.
- The vendor's reply thread lives in Greg's own WhatsApp, invisible to the agent — remind him
  where it lands so he doesn't wait for it in the agent chat.
- The bridge auto-splits long messages (splitLongMessage) — no need to pre-chunk text.
- Greg silences WhatsApp notifications on his phone — for anything time-critical, mirror the ping to Telegram too; WhatsApp alone can sit unread. Full reminder/escalation rules: user-interaction-style skill.
- Greg's WhatsApp voice notes arrive un-transcribed at
`~/.hermes/profiles/johnny/cache/documents/native-inputs/<hash>/aud_*.ogg` — transcribe manually
(Scribe module in /opt/ara); see `references/voice-note-transcription.md`.
- Gateway chat history is NOT recoverable from disk or reliably from session_search: the Baileys
session dir stores only cryptographic key material. If context from a past WhatsApp conversation
is missing (dates, vendor numbers), check once, then re-ask Greg instead of digging.
