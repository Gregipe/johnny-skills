---
name: gmail-api-ops
description: "Use when operating Greg's Gmail: scans, unsubscribes, OAuth."
version: 1.0.0
author: Johnny
license: MIT
metadata:
  hermes:
    tags: [gmail, email, oauth, gmail-api]
    category: email
---

# Gmail API Ops

## When to Use

Any work against Greg's Gmail through the Gmail API: dashboard correspondence refresh and triage,
inbox audits, unsubscribing from lists, drafting replies, re-running OAuth consent.

## Accounts & Files

- Account: gregipe@gmail.com, OAuth client "Johnny CoS" (Greg's own Google Cloud project), scopes gmail.readonly + gmail.compose.
- Connector: `~/johnny-dashboard/gmail_connector.py` — CLI prints JSON, never tokens:
  `profile` | `threads [N]` | `thread <id>` | `draft --to X --subject S --body-file F [--thread-id T]`.
  Run: `uv run --with google-api-python-client --with google-auth python3 gmail_connector.py <cmd>`.
- Tokens: `~/johnny-dashboard/state/gmail_token.json` (chmod 600, gitignored); auto-refresh persists on 401.
- Consent: `~/johnny-dashboard/oauth_setup.py` (InstalledAppFlow loopback; opens a browser for Greg). Run it in background with notify.

## Always-On Rules

- NEVER print token material — print only status booleans or account/profile info.
- NEVER send email via the API. gmail.compose allows drafts only in practice: sending is approval-gated by Greg, every time. DRAFT replies freely; report the draft id.
- A sender is not a list. Subscription identity is the List-ID header — one sender (even one domain) runs MULTIPLE lists, and unsubscribing one leaves the others mailing. Check List-ID on the latest email of each list.
- Unsubscribing = GET on the List-Unsubscribe URL, then VERIFY by loading the URL and reading the vendor's confirmation page. Never trust a subagent's or bridge run's claimed status code — verify the page state yourself.
- Filed state is ground truth: once Greg confirms an item (e.g. "that password reset was me"), never re-flag it from raw email appearance. The recurring trigger is usually an unread scary email — remove the trigger (mark read) instead of re-explaining.
- Bulk scans need quota backoff and batching — see references/api-patterns.md before writing any full-inbox scan.
- OAuth consent failures are consent-screen problems, not code problems — see references/api-patterns.md.

## Support Files

- `references/api-patterns.md` — rate-limit backoff, batched metadata, subscription aggregation, HTML-only bodies, OAuth pitfalls.
- `scripts/subs_audit.py` — 60-day subscription audit (which lists + unread stats, sorted worst-first). Run:
  `uv run --with google-api-python-client --with google-auth python3 <skill_dir>/scripts/subs_audit.py`
- `scripts/html_body_decode.py` — decode HTML-only message bodies for a thread (airline/order/
  newsletter mail whose plain part is empty; `thread` returns body ""). Run:
  `uv run --with google-api-python-client --with google-auth python3 <skill_dir>/scripts/html_body_decode.py <thread_id>`
