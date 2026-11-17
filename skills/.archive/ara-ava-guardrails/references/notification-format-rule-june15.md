# Ava Notification Format Rule (June 15, 2026)

## Hard Rule: All WhatsApp notifications from Ava to Greg use `✨ *Ava :*`

**User correction on June 15:** Greg explicitly asked for the same formatting as every Ava reply — the `✨ *Ava :*` header block. He also wanted labels like "Reminder" in bold.

## Implementation

In `_execute_action` handler for `whatsapp_to_owner` (server.py ~line 7928):

```python
# BEFORE (wrong):
result = wa.send_message_sync(admin.phone, "Ava: " + message)

# AFTER (correct):
result = wa.send_message_sync(admin.phone, "\u2728 *Ava :*\n\n" + message)
```

In `set_reminder` / `create_action_item` tools:

```python
# Notification message format:
notif_msg = f"⏰ **Reminder:** {title}"
# becomes: "✨ *Ava :*\n\n⏰ **Reminder:** Set Timing for Chat (Dinesh Nagar)"
```

## DO NOT:

- Use bare `"Ava: "` prefix — this is a deprecated format
- Omit bold labels on action type words (Reminder, Action, Summary)
- Use the non-emoji format for any owner-facing WhatsApp notification

## Why

Greg's coaching-thread replies all use `✨ *Ava :*` format (server.py ~line 9718). The notification handler was a separate code path using the old bare-prefix format. This created an inconsistent experience — coaching replies looked polished, notifications looked broken.
