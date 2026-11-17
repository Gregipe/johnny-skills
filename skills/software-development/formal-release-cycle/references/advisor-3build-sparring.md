# Advisor Sparring Example — 3-Build Sprint (June 23, 2026)

Real sparring transcript from a 3-build sprint: WhatsApp reminders, KB delete confirmation, and WhatsApp unread marking.

## Round 1: Initial Review — 13 Findings

Advisor found issues across all 3 builds:

### Build 1 (WhatsApp reminders)
1. **[Critical]** `action_type="whatsapp"` routes to lead, not Greg — must use `"whatsapp_to_owner"`
2. **[Critical]** `NameError: 'lead'` — `update_action()` never queries Lead, but payload references `lead.name`
3. **[Important]** Orphan `scheduled_action_id` — FK points to deleted SA, no fallback to create new
4. **[Minor]** Missing `channel="whatsapp"` on new SA
5. **[Minor]** No-op PATCH on unchanged due_at resets fired SA to "pending"

### Build 2 (KB delete)
6. **[Important]** `confirm()` already aliased to `bwConfirm()` — scope was really just message text
7. **[Minor]** `deleteWebsiteDoc()` not found in codebase (later confirmed: exists at L2792)
8. **[Minor]** Catch block uses `bwAlert()` — safe, defined before call site

### Build 3 (WhatsApp unread)
9. **[Critical]** `markChat: 'unread'` does NOT exist in Baileys — correct API is `{ markRead: false, lastMessages: [lastMsg] }`
10. **[Critical]** `lastMessages` parameter is required — WhatsApp silently ignores without it
11. **[Critical]** Python client uses `urllib`, not `requests` — must use `_req()` helper
12. **[Important]** No `sock` null guard — disconnect during `/mark-unread` throws TypeError
13. **[Important]** WhatsApp Web may re-mark as read immediately (multi-device sync conflict)

Outcome: Builds 1 and 3 → CHANGES_REQUESTED, Build 2 → APPROVED

## Round 2: Sparring — Redesigned Build 3

Johnny accepted all Build 1 fixes and redesigned Build 3 with correct Baileys API. Advisor flagged one remaining issue:

- **lastSentMessages lost on restart**: The `lastSentMessages` Map is in-process; lost on crash. Without persistence, `mark_unread_sync()` silently returns `ok: true` with no-op. Fix: persist to JSON file on disk (`last_sent.json`).

## Round 3: Final Approval

- Build 1: CONDITIONALLY APPROVED (verify dispatcher branch + tz-consistency)
- Build 2: CONDITIONALLY APPROVED (confirm `deleteWebsiteDoc()` exists)
- Build 3: CONDITIONALLY APPROVED (fix silent no-op in else branch)

## Key Patterns

1. **Baileys API assumptions are toxic**: Always inspect `node_modules/@whiskeysockets/baileys/lib/Utils/` before claiming an API exists. The advisor checked source code — `chatModificationToAppPatch()` has no `markChat` branch.

2. **Python client uses `_req()`, not `requests`**: A common mistake when adding new methods. The `whatsapp_sidecar_client.py` uses `urllib` via `_req()` helper — never import `requests`.

3. **`confirm()` is aliased to `bwConfirm()` globally**: In dashboard.js, `window.confirm` is overridden at L4993. Any `confirm()` call already uses the custom modal. Scope document should note this.

4. **Orphan FK pattern**: When `scheduled_action_id` points to a deleted record, check for `sa is None` and fall through to creation. The `if action.scheduled_action_id:` guard alone is insufficient.

5. **`action_type` dispatch matters**: `_execute_action()` dispatches `whatsapp_to_owner` to Greg's phone under a specific branch. Using `"whatsapp"` sends to the lead — wrong person.
