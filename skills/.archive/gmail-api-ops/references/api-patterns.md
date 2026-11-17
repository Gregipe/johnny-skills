# Gmail API patterns

## Rate limits — bulk scans burn the per-minute budget

Gmail API 403 "Quota exceeded for 'Total Query Cost'" = the per-user per-minute query budget.
Metadata gets cost ~5 units each, so a full-inbox scan (thousands of messages) exceeds it fast.
Rules for any bulk scan:

- Wrap EVERY list/get call in a retry loop: on 403 / Quota / rateLimit, sleep 55-60s and retry (up to ~6 attempts).
- Sleep 2-5s between batches of 100 metadata gets.
- Never re-run a full scan back-to-back — a second pass inside the same minute guarantees the hit. Cache the result instead.
- 429/403 from Google are transient quota signals, not auth failures — retrying with backoff always resolves them.

## Batched metadata fetch

Use `svc.new_batch_http_request()`: add up to 100 `messages.get(format="metadata")` per batch, each
with a per-message callback stashing (from, list-id, list-unsubscribe, unread = "UNREAD" in labelIds).
Then aggregate. This is the only sane way to profile a mailbox — per-message sequential gets are
order-of-magnitude slower and hit the same quota harder.

## Subscription discovery

- Aggregate by List-ID (the part inside <>) when present, else by From.
- Subscription mail = has List-ID OR List-Unsubscribe header; personal mail has neither.
- Distinguish newsletter lists from compliance/alerts (SBI/NSDL/CDSL/evoting, BSE, bank alerts) —
  never propose unsubscribing the latter, they are account-critical.

## Unsubscribing a list

1. Pull the List-Unsubscribe header from the LATEST email of that specific list.
2. One-click GET on that URL executes the unsubscribe.
3. Verify: load the URL in the browser and read the vendor's page — expect
   "Unsubscribe Successful — You have been removed from: <list name>".
4. After unsubscribing all of a sender's lists, confirm no new mail from any list since the last
   arrival date; a few in-flight messages may still land.

## HTML-only bodies

Commercial mail (order confirmations, most newsletters) often has an EMPTY text/plain part — the
connector's `thread` command only decodes text/plain and returns "". Decode the text/html part
(base64url → strip tags → collapse whitespace) when the body looks empty.

## OAuth pitfalls

- Consent 403 "The app is currently being tested and can only be accessed by developer-approved
  testers" = the signed-in BROWSER account is not on the OAuth consent screen's Test users list,
  or it was added without clicking Save. Fix on the Google Cloud consent screen, not in code.
  The consent page showing the right app name means the client config is fine.
- A hung consent run (browser left open, nobody clicked) never completes: run the flow in
  background with notify so it can wait, and kill the process if Greg reports a stale window.
- gmail.readonly + gmail.compose cannot mark-read/archive/delete/trash. Any mailbox mutation
  needs a re-consent with gmail.modify — ask Greg before expanding scopes.
- gmail.compose technically includes send — the guard against sending is behavioral (approval-gated),
  never rely on the scope to prevent sends.
