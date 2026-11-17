# WhatsApp Notification Format Rule

**Date:** June 15, 2026
**Source:** Explicit user correction — Greg asked "Could you repeat the same formatting as with every Ava reply, which is the block which says Ava with a star and a semicolon? And put Reminder also in bold."

## Rule

All WhatsApp notifications from Ava to Greg must use the same header as coaching replies:

```
✨ *Ava :*

⏰ **Reminder:** Set Timing for Chat (Dinesh Nagar)
```

## Specifics

- **Always use `✨ *Ava :*`** — never the bare `"Ava: "` prefix
- **Bold labels** — `**Reminder:**`, `**Action:**`, `**Summary:**` — for scannability
- **Double newline** after the header (`\n\n`)
- Applies to ALL owner notifications: reminders, cron outputs, action confirmations, system alerts

## Implementation

- `_execute_action` handler for `whatsapp_to_owner`: `"\\u2728 *Ava :*\\n\\n" + message` (server.py ~line 7928)
- `set_reminder` notif_msg: `f"⏰ **Reminder:** {title}"` + optional lead name + description
- `create_action_item` notif_msg: `f"⏰ **Action:** {title}"`

## Verification

Send a test reminder and check WhatsApp — the notification must match the coaching format exactly. If it says "Ava:" (without the sparkle and star), the prefix wasn't updated.
