# Single-Action Guard & Partial Confirmation (June 17, 2026)

Two code-level defenses deployed to server.py to fix over-generation and all-or-nothing rejection.

## Fix 1: Single-Action Guard (`_guard_single_action`)

### Problem

LLM over-generates unsolicited extra tools because the pipeline injection (leads/deals list) primes it to take initiative. User says "send a WhatsApp to Jimmie" — LLM proposes `create_deal` for Shriram Finance too.

### Solution

Inserted after tool calls are generated but before the pending ActionItem is created. Scans the user's message for action verbs and trims multi-tool proposals to match.

```python
def _guard_single_action(user_msg, data_tools):
    """If user asked for ONE action but LLM proposed multiple, trim to matching tool only."""
    # Scans for verbs: send, create, update, change, edit, set, schedule,
    # remind, move, cancel, stop, delete, remove, attach, trigger, start, escalate
    # Maps each verb to allowed tool families
    # If exactly 1 verb found + multiple tools proposed → trims to matching tools
```

**Verb-to-tool mapping:**

| Verb | Allowed Tools |
|------|--------------|
| send | send_whatsapp, send_email, send_whatsapp_to_owner |
| create | create_lead, create_deal, create_action_item |
| update/change/edit | update_lead, update_deal, update_action |
| set/schedule/remind | set_reminder, set_cron, schedule_message, schedule_email |
| move | update_lead_stage, update_deal_stage |
| cancel/stop/delete/remove | cancel_scheduled |
| attach | attach_to_deal |
| trigger/start | trigger_cadence |
| escalate | escalate_to_human |

**Insertion point:** After `_built_desc = _build_pending_description(data_tools)`, before `_pending_row = _AIStore(...)`

**Log signal:** `SINGLE-ACTION-GUARD: trimmed N→M tools (verb=X, kept=[...], dropped=[...])`

## Fix 2: Partial Confirmation (`_split_partial_rejection`)

### Problem

Multi-tool proposals (e.g., create_deal + send_whatsapp) get fully rejected when user says "ignore X, just do Y." The `_classify_confirmation` function returns a single token (confirm/reject/unrelated) — no mechanism for partial confirmation. "Ignore Shriram, do WhatsApp" → classifier returns `reject` → everything cancelled.

### Solution

Before the all-or-nothing reject handler, scan the user's reply for "ignore X" / "just do Y" patterns. Match entity names against pending tool call args. Split into keep vs reject. Execute kept tools, drop rejected ones.

```python
def _split_partial_rejection(user_msg, pending_tool_calls):
    """Parse 'ignore X, just do Y' and return (keep_tools, reject_tools)."""
    # Pattern 1: "ignore X", "skip X" → skip_entity
    # Pattern 2: "just do Y", "only Y" → keep_entity
    # Match entities against tool args (lead_name, org_name, deal_name, etc.)
    # Return (keep, reject) or (None, None) if no partial pattern detected
```

**Entity matching:** Checks tool call args (`lead_name`, `org_name`, `deal_name`, `name`, `title`, `message`) for substring match against the parsed entity from user's reply.

**Insertion point:** In the `elif _verdict == "reject":` handler, before the cancel-all block.

**Log signal:** `PARTIAL-REJECT: keeping=N tools, rejecting=M tools (skip=X, keep=Y)`

**Fallback:** If all tools are rejected (empty keep) or no partial pattern detected → normal full reject.

## Verified Behavior (June 17, 2026)

**Before fixes:**
- "send WhatsApp to Jimmie" → proposed create_deal (Shriram) + send_whatsapp
- "Ignore Shriram, just do WhatsApp" → everything cancelled

**After fixes:**
- "send WhatsApp to Jimmie" → proposed ONLY send_whatsapp (guard trimmed create_deal)
- "Ignore Shriram, just do WhatsApp" → would execute WhatsApp only (partial confirmation)
