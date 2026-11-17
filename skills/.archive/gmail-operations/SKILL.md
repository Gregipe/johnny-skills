---
name: gmail-operations
description: "Use when connecting or operating Greg's Gmail (Gmail API)."
version: 1.0.0
author: Johnny
license: MIT
metadata:
  hermes:
    tags: [gmail, email, oauth, connector]
    category: productivity
---

# Gmail Operations (Gmail API)

Owns the provider mechanics for Greg's Gmail API usage (the Johnny CoS dashboard connector and any future Gmail tooling). Triage policy lives in email-inbox-triage; this skill owns commands, consent, and scopes.

## When to Use

- Connect or reconnect Gmail OAuth for any of Greg's local tools
- Pull, read, or draft against Greg's inbox via the connector
- Unsubscribe Greg from a newsletter
- Debug Gmail API issues: consent 403s, scope gaps, empty message bodies, re-alarming triage

## Connector (current deployment)

- `~/johnny-dashboard/gmail_connector.py` — prints JSON to stdout, never tokens. Commands: `profile` | `threads [N]` | `thread <id>` | `draft --to X --subject S --body-file F [--thread-id T]`
- Run: `cd ~/johnny-dashboard && uv run --with google-api-python-client --with google-auth python3 gmail_connector.py <cmd>`
- Tokens: `state/gmail_token.json` (chmod 600, gitignored; auto-refreshed and persisted on 401). Account: gregipe@gmail.com, OAuth client "Johnny CoS".

## OAuth consent (oauth_setup.py)

- Run it as `terminal(background=true, notify=true)` — a foreground timeout kills the flow mid-consent and leaves no token file; the consent takes as long as Greg takes.
- Desktop client, loopback redirect (127.0.0.1, random port), `access_type=offline` + `prompt=consent` so a refresh_token is always returned.
- Consent 403 "The app is currently being tested and can only be accessed by developer-approved testers" = the signed-in account is not a registered Test User. Fix: in the SAME project, OAuth consent screen → Test users → Add Users → **Save** (Save is the step that gets missed). Also fires when the browser is signed into a different Google account, or the OAuth client was created in a different project than the one holding the test user.
- Never print token material to output — write straight to file and chmod 600.

## Scope facts

- `gmail.readonly` + `gmail.compose` covers reading and creating drafts. There is NO draft-without-send scope — compose technically permits sending, so the no-send rule is behavioral (Greg's approval gates every send), not scope-enforced. Do not lean on the scope as a safety rail.
- Marking read / archiving / label changes needs `gmail.modify`, which is not held. Consequence: unread security-looking emails (password resets, login alerts) stay unread forever, and every fresh `threads` pull re-alarms the triage — even after Greg confirmed the event was his. Options: Greg marks them read manually, or re-run consent with gmail.modify added. Either way, carry the filed note forward in triage state.

## HTML-only bodies

Many transactional and newsletter emails carry no text/plain part; `thread <id>` then returns an empty body. Walk the payload parts recursively for `text/html`, base64-decode it, and strip tags with a regex — that is the whole workaround.

## Unsubscribing a newsletter

1. Fetch the thread `format=full` and read the `List-Unsubscribe` header — the one-click URL is there even when body links hide behind tracking redirects.
2. GET that URL (browser works; `List-Unsubscribe-Post: One-Click` accepts GET on most ESPs).
3. Verify the CONFIRMATION PAGE text says the unsubscribe succeeded — never report done off an HTTP status alone, and never claim a status code you did not actually observe.
4. Record it in triage state ("Unsubscribed (one-click, verified)") so later refreshes and agents know it is done.
- ESPs run separate lists: a later email from the same publisher may be a different list — unsubscribe each occurrence; the earlier one stays done.

## Ground truth for triage state

Filed/confirmed items are settled: never re-flag them from a fresh raw pull, even when the raw email matches an alarm pattern (a "password reset = phishing" pattern refires on the same thread every pull). Reconcile fresh data against existing triage notes before raising any new flag.
