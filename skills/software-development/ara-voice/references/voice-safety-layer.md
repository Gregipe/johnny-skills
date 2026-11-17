# Voice Safety Layer — Voice-Read + Text-Confirm

## The Problem

ARA's text-channel safety mechanisms (confirmation gate, honest-narration, state-consistency) are all designed around text affordances. Voice removes all four:

| Affordance | Text Channel | Voice |
|---|---|---|
| Persistence | ActionItem row, TTL-gated | Spoken words evaporate |
| Inspectability | Parse tool-call JSON before sending | Can't parse before TTS speaks it |
| Retractability | Swap response before sending | Once spoken, can't un-say |
| Async confirmation | User types "yes" → regex classify | Must respond immediately; backchannel "yeah" ≠ confirmation |

Voice adds **mishearing** (STT errors on Hindi/code-switching/accents/noisy lines).

## V1 Solution: Voice-Read + Text-Confirm

Voice agent READS CRM data and PROPOSES writes. Write-confirmation stays in WhatsApp text channel.

```
Field rep (voice):  "Move Acme to closed-won"
Ava (voice):        "Got it. Check WhatsApp to confirm."
Ava (WhatsApp):     "⏳ Confirm: Move Acme → closed-won. Reply yes."
Field rep (text):   "yes"
Ava (WhatsApp):     "✅ Done."
```

## Three Mandatory Safety Constraints

### 1. ANI Scope-Locking
Voice agent can ONLY read data for the authenticated caller's phone number. If a customer asks about another account, redirect to text: "I can only discuss your account over voice — please message us on WhatsApp."

### 2. Draft-and-Link Pattern
- Voice agent creates a DRAFT write (not committed) with a short ID
- Agent speaks: "I've drafted an update. Confirm via WhatsApp."
- WhatsApp message with confirm/reject buttons
- Only button-tap commits
- Drafts expire in 10 minutes
- Must be built in Phase 1, not deferred

### 3. Full Transcript Logging
- STT transcript (both sides) → CRM call notes
- Agent's intended actions → audit log
- Call metadata (duration, timestamp, ANI) → CRM call history
- Pipecat supports this natively (frame-based pipeline)

## Gaps to Address

1. **Data exfiltration via mishearing**: STT mishears name → reads wrong customer data. Mitigated by ANI scope-locking.
2. **Voice→text handoff UX**: User hangs up before confirming. Mitigated by draft-and-link + expiry.
3. **Barge-in during sensitive reads**: Interrupted mid-read of account data — did caller hear it? Log partial transcripts for audit.

## Voice-Initiated Writes (Phase 3, Future)

Gated behind:
- Phase 2 draft-confirm proven stable (500+ calls, > 90% reliability)
- Spoken confirmation UX designed and tested
- False-confirmation rate measured < 1%
