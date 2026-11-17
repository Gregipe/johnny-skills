# Code-Level Intent Guards (June 17, 2026)

These guards run in the observe loop and supplement the classification framework.
They are safety nets, not primary classification mechanisms.

## Single-Action Guard (`_guard_single_action`)

**Location:** `server.py`, called in the observe loop before pending ActionItem creation.

**What it does:** Scans the user's message for action verbs (send, create, update, set, schedule, etc.). If exactly ONE verb is found but the LLM proposed MULTIPLE data-modifying tools, trims to only the matching tools.

**Example:** Greg says "send a WhatsApp to Jimmie" → verb "send" found → LLM proposed [create_deal, send_whatsapp] → guard trims to [send_whatsapp].

**When it does NOT fire:**
- Multi-verb requests ("create a deal and send a WhatsApp") → both verbs found, no trimming
- Read-only tools only → guard only checks data-modifying tools
- All tools match the verb → no trimming needed
- No verb found → no trimming

**Verb-to-tool mapping:**
```
send     → send_whatsapp, send_email, send_whatsapp_to_owner
create   → create_lead, create_deal, create_action_item
update   → update_lead, update_deal, update_action
change   → update_lead, update_deal, update_action
edit     → update_lead, update_deal, update_action
set      → set_reminder, set_cron
schedule → set_reminder, set_cron, schedule_message, schedule_email
move     → update_lead_stage, update_deal_stage
cancel   → cancel_scheduled
attach   → attach_to_deal
trigger  → trigger_cadence
```

**Logging:** `SINGLE-ACTION-GUARD: trimmed N→M tools (verb=X, kept=[...], dropped=[...])`

## Partial Confirmation (`_split_partial_rejection`)

**Location:** `server.py`, called in the reject verdict handler before full cancellation.

**What it does:** When the user says "ignore X, just do Y" to a multi-tool proposal, parses the reply to identify which tools to reject and which to keep. Executes the kept tools, drops the rejected ones.

**Example:** Pending proposal has [create_deal(Shriram Finance), send_whatsapp(Jimmie Tete)]. Greg says "Ignore the shriram finance deal for now and just handle the whatsApp to Jimmie please." → skip_entity="shriram finance deal" → matches create_deal → dropped. send_whatsapp doesn't match → executed.

**Entity matching:** Tool call args (lead_name, org_name, deal_name, name, title, message) are compared against the user's "ignore" and "keep" entities. Case-insensitive substring matching.

**When it does NOT fire:**
- Single-tool pending → returns None (fall through to normal reject)
- No partial-rejection pattern detected → returns None
- All tools matched by "ignore" → returns None (fall through to normal reject)

**Logging:** `PARTIAL-REJECT: keeping=N tools, rejecting=M tools (skip=[...], keep=[...])`

## Hypothetical Guard (REMOVED — reverted)

An attempted `_is_hypothetical_question` function using regex patterns was added then reverted. Greg explicitly rejected pattern matching: "Is that not happening and are we still relying on some set of terms and patterns?"

The CLASSIFY INTENT FIRST framework now handles hypothetical detection through LLM reasoning instead of code-level pattern matching.

## Relationship to Classification Framework

These guards are BELOW the classification layer. The classification framework in the system prompt is the primary defense. These guards catch cases where:
1. The LLM correctly classifies a COMMAND but over-generates tools (single-action guard)
2. The confirmation classifier returns "reject" but the user meant partial rejection (partial confirmation)

They should NOT grow into pattern-matching engines. If a new guard requires a growing list of regex patterns or keyword sets, the fix belongs in the classification framework instead.
