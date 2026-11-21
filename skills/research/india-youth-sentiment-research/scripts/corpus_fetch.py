#!/usr/bin/env python3
"""Fetch a subreddit's posts for a date window from arctic-shift (or probe pullpush).
Usage: python3 corpus_fetch.py SUBREDDIT YYYY-MM-DD YYYY-MM-DD OUT.json [cap]
Saves posts as [{id,title,selftext,created_utc}]. Paginates desc within window.
Note: cache/scratch is pruned after ~24h idle — re-fetch when re-running analyses.
"""
import requests, json, sys, time, datetime

AR = "https://arctic-shift.photon-reddit.com/api/posts/search"
PP = "https://api.pullpush.io/reddit/search/submission/"

def probe_pullpush(sub, after_iso, before_iso):
    r = requests.get(PP, params=dict(subreddit=sub, size=100, sort="desc", sort_type="created_utc",
                                     after=after_iso, before=before_iso), timeout=60)
    return r.json().get("data", [])

def fetch_arctic(sub, a_iso, b_iso, cap=1000):
    a_e = int(datetime.datetime.fromisoformat(a_iso).replace(tzinfo=datetime.UTC).timestamp())
    b_e = int(datetime.datetime.fromisoformat(b_iso).replace(tzinfo=datetime.UTC).timestamp())
    posts, seen, cur = [], set(), b_e
    while len(posts) < cap and cur > a_e:
        d = None
        for _ in range(3):
            try:
                r = requests.get(AR, params=dict(subreddit=sub, after=a_e, before=cur,
                                                 limit=100, sort="desc"), timeout=45)
                d = r.json(); break
            except Exception:
                time.sleep(2)
        if d is None: time.sleep(4); continue
        data = d.get("data", [])
        if data:
            new = [x for x in data if x.get("id") not in seen]
            seen.update(x.get("id") for x in new); posts.extend(new)
            last = min(x.get("created_utc") for x in data)
            cur = last if last < cur else cur - 3600
        else:
            cur -= 3600
        time.sleep(0.7)
    posts.sort(key=lambda x: x["created_utc"], reverse=True)
    return posts

def fetch_comments(post_id, limit=100):
    """Arctic comments for a thread: link_id=t3_<id>. Full coverage even where post fetch is limited."""
    r = requests.get("https://arctic-shift.photon-reddit.com/api/comments/search",
                     params=dict(link_id="t3_" + post_id, limit=limit), timeout=45)
    return r.json().get("data") or []

if __name__ == "__main__":
    sub, a_iso, b_iso, out = sys.argv[1:5]
    cap = int(sys.argv[5]) if len(sys.argv) > 5 else 1000
    ps = fetch_arctic(sub, a_iso, b_iso, cap)
    clean = [{"id": x.get("id"), "title": x.get("title") or "",
              "selftext": (x.get("selftext") or "")[:600], "created_utc": x.get("created_utc")} for x in ps]
    json.dump(clean, open(out, "w"))
    if clean:
        d0 = datetime.datetime.fromtimestamp(clean[-1]["created_utc"], datetime.UTC).date()
        d1 = datetime.datetime.fromtimestamp(clean[0]["created_utc"], datetime.UTC).date()
        print(f"{sub}: {len(clean)} posts, {d0}..{d1} -> {out}")
    else:
        print(f"{sub}: EMPTY")

# PITFALLS (learned the hard way):
# - arctic has NO full-text 'q' param (400 error); pullpush has 'q' but spotty sub coverage (has IndiaCareers 2026, NOT pfi/IF/developersIndia).
# - Dense subs (developersIndia ~200+/day): cap-1000 desc covers only the LAST FEW DAYS of any window. For older windows, locate threads via web_search (site:reddit.com/r/<sub> <keywords>) then fetch their comments with fetch_comments().
# - Every fetch: report the corpus's actual covered date range; density differences are findings.
# - 2025 corpora: check avg selftext length before trusting cross-year % dips.
