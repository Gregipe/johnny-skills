---
name: apple
description: "Apple/macOS automation — Notes, Reminders, FindMy, iMessage, and macOS desktop control."
category: productivity
trigger: Apple ecosystem integration; Notes, Reminders, FindMy, iMessage, macOS automation
---

# Apple Skills

Complete guide to Apple/macOS automation and integration.

## Overview

This skill consolidates:
1. **Notes** — Apple Notes management
2. **Reminders** — Apple Reminders management
3. **FindMy** — Device and AirTag tracking
4. **iMessage** — Send/receive iMessages
5. **macOS Desktop** — Background automation

---

## 1. Notes

### CLI Tool

Uses the `memo` CLI for Apple Notes access.

### Operations

```bash
# List notes
memo list

# Create note
memo create --title "Meeting Notes" --content "Discussion points..."

# Search notes
memo search "keyword"
```

---

## 2. Reminders

### CLI Tool

Uses `remindctl` for Apple Reminders.

### Operations

```bash
# List reminders
remindctl list

# Add reminder
remindctl add --title "Call mom" --due "2024-12-25"

# Complete
remindctl complete <id>
```

---

## 3. FindMy

### App Integration

Uses FindMy.app on macOS for device/AirTag tracking.

### Operations

Locate devices via the FindMy map interface.

---

## 4. iMessage

### CLI Tool

Uses `imsg` CLI for iMessage.

### Operations

```bash
# Send message
imsg send "+1234567890" "Hello!"

# List conversations
imsg list
```

---

## 5. macOS Desktop

### Computer Use

Drive macOS desktop in background:
- Screenshot capture
- Mouse/keyboard automation
- UI element interaction

---

## References

- `references/` — Additional documentation