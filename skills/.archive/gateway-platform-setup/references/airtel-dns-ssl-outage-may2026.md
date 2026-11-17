# Airtel DNS/SSL Outage — May 19-20, 2026

## Timeline

| Date/Time (IST) | Event | Evidence |
|----------------|-------|----------|
| May 19 ~07:31 | **Tavily web_search SSL timeout** (all 3 parallel requests) | `plugins.web.tavily.provider: Tavily search error: _ssl.c:999: The handshake operation timed out` |
| May 19 ~07:32 | **web_extract fails** — zero content from YC/Verge | `tools.web_tools: https://news.ycombinator.com/ (no content to process)` |
| May 19 ~07:33 | **Local file reads work fine** — not a disk issue | `read_file returned error ... File not found` (only missing files, not systemic) |
| May 19 ~16:17 | **Telegram DNS failure** — 8 retries over 31 seconds | `[Errno 8] nodename nor servname provided, or not known` → fallback IP fail |
| May 19 ~16:19 | **Telegram recovers** via sticky fallback IP | `[Telegram] Primary api.telegram.org path unreachable; using sticky fallback IP 149.154.166.110` |
| May 19 ~19:18 | **Telegram httpx.ReadError** | `[Telegram] Telegram network error, scheduling reconnect: httpx.ReadError` |
| May 19 ~19:54 | **Telegram resumes** after 2 reconnect attempts | `[Telegram] Telegram polling resumed after network error (attempt 2)` |
| May 20 ~06:17 | **User message processed normally** | Gateway processes "John you there?" |
| May 20 ~06:22 | **Gateway crashes silently** after 46h uptime | Process PID 38579 gone — no exit diagnostic — launchd auto-restarted |

## Common Thread

All failures point to **Airtel DNS resolver intermittency**, not a gateway bug:

1. **DNS failures** — `nodename nor servname provided, or not known` is macOS's DNS resolution failure message. The gateway's Telegram module tried 8 times (primary + 3 fallback IPs) before either recovering or timing out.

2. **SSL handshake timeouts** — `_ssl.c:999: The handshake operation timed out` on Tavily occurred because the DNS could not resolve the Tavily API server, or resolved slowly enough that the SSL handshake timer expired (60s default).

3. **ReadErrors** — `httpx.ReadError` on Telegram was likely a connection reset mid-stream after the DNS temporarily resolved, then dropped.

## Key Diagnostic Commands

```bash
# Check gateway log for DNS failures
grep "nodename\|ssl\|Timeout\|ReadError" ~/.hermes/profiles/johnny/logs/gateway.log | grep "2026-05-19"

# Check errors log for Tavily/web failures in the same window
grep "2026-05-19" ~/.hermes/profiles/johnny/logs/errors.log | grep -i "ssl\|handshake\|timeout"

# Multi-target connectivity test
for host in api.telegram.org tavily.io api.openai.com github.com; do
    echo -n "DNS $host: "
    dig +short $host 2>&1 || echo "FAIL"
    echo -n "SSL $host: "
    curl -sI --max-time 5 https://$host 2>&1 | head -1 || echo "FAIL"
done

# Test with Google DNS to isolate ISP resolver
dig @8.8.8.8 api.telegram.org +short
dig @1.1.1.1 api.telegram.org +short
```

## What to Look For in Future

When a user reports "Telegram went down" or "the morning briefing didn't include news":

1. **Check if multiple services failed simultaneously** — Telegram DNS + Tavily SSL + web_extract failures in the same time window = ISP issue, not gateway
2. **The agent handles this gracefully** — the May 19 morning briefing completed and delivered despite zero web data, using local context
3. **No gateway config change fixes this** — it's upstream of the machine. The gateway's Telegram fallback IP (`149.154.166.110`) is the best built-in recovery mechanism
4. **Cron briefings may be sparse** during these windows but will still deliver
