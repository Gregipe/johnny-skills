"""60-day Gmail subscription audit: which lists is Greg on, and how unread are they?

Aggregates by List-ID (fallback: From) over all messages from the last 60 days,
using batched metadata requests with quota backoff. Prints JSON to stdout,
progress to stderr. Import expects gmail_connector.py next to ~/johnny-dashboard.

Run: uv run --with google-api-python-client --with google-auth python3 subs_audit.py
"""
import json
import sys
import time
from collections import defaultdict

sys.path.insert(0, "/Users/greg/johnny-dashboard")
from gmail_connector import _creds, _service  # noqa: E402

creds = _creds()
svc = _service(creds)


def _retry(fn, what):
    for _attempt in range(6):
        try:
            return fn()
        except Exception as e:
            if "429" in str(e) or "Quota" in str(e) or "rateLimit" in str(e):
                print("%s quota hit, sleeping 60s..." % what, file=sys.stderr)
                time.sleep(60)
            else:
                raise
    raise RuntimeError("quota retries exhausted on %s" % what)


# 1) collect all message ids from last 60 days
ids = []
page = None
while True:
    kw = dict(userId="me", q="newer_than:60d", maxResults=500)
    if page:
        kw["pageToken"] = page
    res = _retry(lambda: svc.users().messages().list(**kw).execute(), "list")
    ids.extend(m["id"] for m in res.get("messages", []))
    page = res.get("nextPageToken")
    if not page:
        break

print("TOTAL_MESSAGES_60D:", len(ids), file=sys.stderr)

# 2) batched metadata gets: id -> (from, list_id, has_unsub, unread)
stats = {}
batch = svc.new_batch_http_request()


def make_cb(mid):
    def cb(request_id, response, exception):
        if exception:
            return
        p = response.get("payload", {})
        hdrs = {h["name"].lower(): h["value"] for h in p.get("headers", [])}
        unread = "UNREAD" in response.get("labelIds", [])
        stats[mid] = (hdrs.get("from", ""), hdrs.get("list-id", ""),
                      bool(hdrs.get("list-unsubscribe")), unread)
    return cb


for i, mid in enumerate(ids):
    batch.add(svc.users().messages().get(userId="me", id=mid, format="metadata"),
              callback=make_cb(mid))
    if (i + 1) % 100 == 0 or i == len(ids) - 1:
        _retry(batch.execute, "batch")
        batch = svc.new_batch_http_request()
        time.sleep(2)
        print("batch %d/%d" % (min(i + 1, len(ids)), len(ids)), file=sys.stderr)

# 3) aggregate subscription mail (has List-ID or List-Unsubscribe)
subs = defaultdict(lambda: [0, 0, ""])  # key -> [total, unread, from]
for _mid, (frm, list_id, has_unsub, unread) in stats.items():
    if not list_id and not has_unsub:
        continue  # not subscription mail
    key = list_id.split("<")[-1].split(">")[0] if "<" in list_id else (list_id or frm)
    subs[key][0] += 1
    subs[key][1] += unread
    subs[key][2] = frm

out = []
for key, (total, unread, frm) in subs.items():
    out.append({"list": key, "from": frm, "emails": total, "unread": unread,
                "unread_pct": round(100.0 * unread / total)})
out.sort(key=lambda x: (-x["unread"], -x["emails"]))

json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
