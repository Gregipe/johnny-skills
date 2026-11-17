# Echo Gate Infinite Confirmation Loop — June 29, 2026

## Symptom

User sends "yes" to confirm a pending WhatsApp send. The agent repeats the same confirmation prompt ("⏳ Waiting for you — reply yes to confirm or no to cancel") indefinitely. Every "yes" is ignored.

## Root Cause

`_is_echo_message()` (Issue #2 fix, deployed at commit `bc0a3c6`) has a content-match check that compares the user's message against recent assistant messages:

```python
if _rm.content.strip()[:100] in stripped or stripped[:100] in _rm.content.strip():
    return True
```

The second clause `stripped[:100] in _rm.content.strip()` means: if the user typed "yes" (3 chars), and any recent assistant message contains the word "yes" → echo detected.

The assistant's confirmation prompt is:
> ⏳ Waiting for you — reply **yes** to confirm or no to cancel:

So "yes" is always a substring match → echo gate fires → `_live = None` → pending action is never consumed.

## Log Evidence

```
Jun 29 13:36:38 CONFIRM-FLOW created-pending: id=c6f7ab92 tools=[{...send_whatsapp...}]
Jun 29 13:36:41 CONFIRM-FLOW echo-detected: suppressing classification, msg[:80]=yes
```

After that, every ~7 seconds for 20+ minutes:
```
CONFIRM-FLOW live-pending: id=c6f7ab92 title=... shall I send it?
CONFIRM-FLOW verdict: None for pending id=c6f7ab92
```

`_live = None` prevents `_live_pending_for_tenant()` from being called, so the pending stays `awaiting_approval` forever. The classifier never sees the "yes" confirmation.

## Why the Prefix Check Didn't Help

The prefix regex check (`_ECHO_PATTERN`) correctly rejects "yes" — it doesn't match any prefix. But content-match runs AFTER, and the second clause catches it. There's no short-circuit after prefix mismatch.

## Deployed Fix — June 29, 2026 (commit `4afe801`)

Two root causes were discovered and fixed:

### Fix 1: Content-match minimum length guard

```python
# In _is_echo_message(), before content-match:
if len(stripped) >= 40:  # Only check long messages (real copy-pastes are 40+ chars)
    if _rm.content.strip()[:100] in stripped or stripped[:100] in _rm.content.strip():
        return True
```

The threshold is 40 characters — not 10. Real copy-pasted assistant messages are multi-line paragraphs. Short confirmations like "yes", "yes to both", "go ahead" (all under 20 chars) will never trigger the content-match path. The prefix regex path still catches formatting-borne echoes.

### Fix 2: _classify_confirmation output hardening

The LLM classifier often returned noisy output like `"confirm.\n"` or `"confirm\n\n"` which failed the raw string comparison against `"confirm"` — defaulting to `"unrelated"`. Fix: extract first token and strip punctuation before validation:

```python
raw = call_llm(_prompt, temperature=0.0)
token = (raw or "").strip().lower().split()[:1]
token = token[0].strip(".,!?:;\"'") if token else ""
return token if token in ("confirm", "reject", "unrelated") else "unrelated"
```

This was the reason `verdict: None` appeared in logs — even when the echo gate was NOT triggered (e.g., tests hitting Rajesh Sharma), the classifier returned noisy output that fell through to `unrelated`.

### Verification

```
Before: "yes" → echo-detected → _live = None → verdict: None → infinite loop
After:  "yes" → live-pending FOUND → verdict: confirm → WhatsApp sent ✅

Log proof:
Jun 29 15:36:46 CONFIRM-FLOW live-pending: id=12dc1d1e (FOUND, not echo-suppressed)
Jun 29 15:36:48 CONFIRM-FLOW verdict: confirm for pending id=12dc1d1e
Jun 29 15:36:48 CONFIRM-FLOW executing: 1 tool(s)
```

## Verbatim Transcript Snippet

```
Shall I send both?
→ Yes.
→ ⏳ Waiting for you — reply yes to confirm or no to cancel:
   💬 Send WhatsApp to Arun Naik — "..."; 💬 Send WhatsApp to Sai Bharat — "..."
→ Yes.
→ ⏳ Waiting for you — reply yes to confirm or no to cancel:
   (same)
→ Yes to both
→ (same)
```
