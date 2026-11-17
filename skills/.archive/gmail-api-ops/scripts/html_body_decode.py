"""Decode HTML-only Gmail message bodies for a thread.

The connector's `thread` command only decodes text/plain; commercial mail
(airlines, order confirmations, newsletters) often has an empty plain part and
returns body "". This prints the tag-stripped text of every text/html part.

Usage (from any dir — it path-inserts the dashboard for the connector):
  uv run --with google-api-python-client --with google-auth python3 \
    <skill_dir>/scripts/html_body_decode.py <thread_id>

Never prints token material — only decoded body text.
"""
import sys, re, html, base64
sys.path.insert(0, "/Users/greg/johnny-dashboard")
import gmail_connector as gc


def walk(p):
    texts = []
    if p.get("mimeType") == "text/html" and p.get("body", {}).get("data"):
        texts.append(base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", "replace"))
    for part in p.get("parts", []):
        texts.extend(walk(part))
    return texts


def main():
    if len(sys.argv) != 2:
        print("usage: html_body_decode.py <thread_id>")
        sys.exit(2)
    tid = sys.argv[1]
    creds = gc._creds()
    svc = gc._service(creds)
    full = gc._call(creds, lambda: svc.users().threads().get(
        userId="me", id=tid, format="full").execute())
    for m in full.get("messages", []):
        hdrs = gc._hdrs(m)
        print("===", hdrs.get("From", ""), "|", hdrs.get("Date", ""), "===")
        for body in walk(m.get("payload", {})):
            txt = re.sub(r"<style.*?</style>", " ", body, flags=re.S)
            txt = re.sub(r"<[^>]+>", " ", txt)
            txt = html.unescape(txt)
            txt = re.sub(r"\s+", " ", txt)
            print(txt[:4000])
            print("---")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"error: {type(e).__name__}: {e}")
        sys.exit(1)
