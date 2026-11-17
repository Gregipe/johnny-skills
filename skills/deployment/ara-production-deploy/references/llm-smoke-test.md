# LLM Smoke Test (`scripts/llm-smoke.sh`)

## Purpose
Verifies DeepSeek API is reachable and the API key is valid. Used as both a deploy gate and a cron watchdog.

## Behavior
- **Silent on 200** — exit 0, no output. Cron uses this for "nothing to report."
- **Alerts on non-200** — prints error + exit 1. Deploy aborts. Cron delivers alert.

## Script
```bash
#!/bin/bash
set -e
for f in /root/.hermes/.env /opt/ara/.env; do
    [ -f "$f" ] && source "$f" 2>/dev/null || true
done
API_KEY="${DEEPSEEK_API_KEY:-}"
[ -z "$API_KEY" ] && echo "⚠️ DEEPSEEK_API_KEY not set" && exit 1

RESP=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST https://api.deepseek.com/v1/chat/completions \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"hi"}],"max_tokens":5}' \
    --max-time 15 2>/dev/null)

[ "$RESP" = "200" ] && exit 0
echo "⚠️ DeepSeek API is unreachable (HTTP $RESP). LLM features are down."
exit 1
```

## Integration
- `/opt/ara/deploy.sh` step 7 — blocks deploys if LLM is dead
- Cron `edf6e7804f1d` — runs every 15m, silent when healthy

## Key expired incident (June 14, 2026)
Key `sk-e05b9ee0fc54...` in `/root/.hermes/.env` expired at ~1:10 AM June 14. Journal showed 200 OK until June 13 2:14 PM, then 401. All LLM features (WhatsApp, email auto-respond, Ava chat, cadence gen) were silently dead. The cron watchdog would have alerted within 15 minutes of the first failure — but it wasn't in place yet. Now it is.
