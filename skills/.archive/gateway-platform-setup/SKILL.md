---
name: gateway-platform-setup
description: "Set up messaging platforms (Discord, Telegram, Slack, etc.) for the Hermes gateway — env vars, config, auth allowlists, restart patterns, and common pitfalls."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [discord, telegram, slack, gateway, platform, setup, auth, allowlist]
---

# Gateway Platform Setup

Class-level skill for adding a messaging platform to the Hermes gateway. Covers env var setup, config entries, allowlist gotchas, and gateway lifecycle.

## Platform Checklist (generic)

For every platform, you need:

| What | Where | Example |
|------|-------|---------|
| **Bot token/credential** | Profile `.env` | `DISCORD_BOT_TOKEN=xxx` |
| **Allowed users** | Profile `.env` | `DISCORD_ALLOWED_USERS=user_id1,user_id2` |
| **Enabled flag** | Profile `config.yaml` | `discord.enabled: true` |
| **Channel prompts** (optional) | Profile `config.yaml` | Per-channel system prompts |
| **Home channel** (optional) | Profile `.env` | Cron delivery target |

## Critical: Profile vs Main Config Distinction

The gateway runs with `--profile <name>`, so `HERMES_HOME` resolves to `~/.hermes/profiles/<name>/`. This means:

- **Profile `.env`** (`~/.hermes/profiles/<name>/.env`) is what the gateway actually reads — NOT `~/.hermes/.env`
- **Profile `config.yaml`** (`~/.hermes/profiles/<name>/config.yaml`) — same logic
- The main config at `~/.hermes/config.yaml` is only used when running WITHOUT `--profile`

**Pitfall:** Adding a bot token or allowed users to the MAIN `.env` and wondering why the profile-based gateway doesn't pick it up. Always put platform credentials in the PROFILE's `.env`.

## Per-Platform Env Vars

| Platform | Token Var | Allowed Users Var | Allow All Var |
|----------|-----------|-------------------|---------------|
| Discord | `DISCORD_BOT_TOKEN` | `DISCORD_ALLOWED_USERS` | `DISCORD_ALLOW_ALL_USERS` |
| Telegram | `TELEGRAM_BOT_TOKEN` | `TELEGRAM_ALLOWED_USERS` | `TELEGRAM_ALLOW_ALL_USERS` |
| Slack | `SLACK_BOT_TOKEN` | `SLACK_ALLOWED_USERS` | `SLACK_ALLOW_ALL_USERS` |
| WhatsApp | (Baileys pairing) | `WHATSAPP_ALLOWED_USERS` | `WHATSAPP_ALLOW_ALL_USERS` |
| Signal | `SIGNAL_NUMBER` | `SIGNAL_ALLOWED_USERS` | `SIGNAL_ALLOW_ALL_USERS` |

## The Allowlist Trap (Critical)

**If `DISCORD_ALLOWED_USERS` (or any platform's allowed users var) is NOT set, the gateway will DENY ALL USERS by default.**

The bot will connect fine, show as online, but every user message will be silently dropped with a log like:
```
WARNING gateway.run: Unauthorized user: USER_ID (USERNAME) on discord
```

This IS NOT an auth failure — the token is valid, the bot is connected. It's the allowlist being empty.

**Fix:** Add the correct env var with the user's platform-specific user ID:
```
DISCORD_ALLOWED_USERS=1002523983352180756
```

**Finding user IDs:**
- Discord: Enable Developer Mode → right-click user → Copy ID
- Telegram: Message @userinfobot
- Check the gateway logs — the unauthorized warning includes the user ID

## Platform-Specific Setup

### Discord

**Config entries** (in profile `config.yaml` under `discord:`):
```yaml
discord:
  enabled: true
  require_mention: false
  free_response_channels: ''      # Comma-separated channel IDs for free response
  allowed_channels: ''             # Restrict to specific channels (empty = all)
  auto_thread: true                # Auto-create threads for conversations
  reactions: true                  # React to messages
  server_actions: ''               # Moderation actions
  channel_prompts:
    CHANNEL_ID:
      prompt: |-
        Channel-specific system prompt here
```

**Opus codec warning** — Harmless:
```
WARNING gateway.platforms.discord: Opus codec not found — voice channel playback disabled
```
This just means voice channel playback won't work. Text messaging is unaffected.

### Telegram

**Config entries** (in `config.yaml`):
```yaml
telegram:
  enabled: true
  reactions: false
  channel_prompts: {}
```

### Slack

Requires both `SLACK_BOT_TOKEN` (xoxb-...) and `SLACK_APP_TOKEN` (xapp-...) for Socket Mode.

## Gateway Restart Patterns

After changing env vars or config, the gateway needs restarting:

### Via launchctl (macOS)
```bash
# Find the service name
launchctl list | grep hermes

# Kill the process — launchd restarts it automatically
# (for services with KeepAlive / Restart on failure)
kill <PID>

# If that doesn't work, bootout and load
launchctl bootout gui/$(id -u)/ai.hermes.gateway-<profile>
launchctl load ~/Library/LaunchAgents/ai.hermes.gateway-<profile>.plist
```

### Verify restart
```bash
ps aux | grep 'gateway run'
# Check logs
tail -5 ~/.hermes/profiles/<profile>/logs/gateway.log
```

### Crash / Hang Diagnosis

When a platform goes down, the gateway process may still be alive or may have already been replaced by launchd. Use these steps systematically:

**1. Check process liveness**
```bash
ps aux | grep "gateway run" | grep -v grep
# Look for: python -m hermes_cli.main --profile <name> gateway run --replace
```
Note the PID and start time. If the PID is different from what you last noted, launchd already replaced it.

**2. Test network connectivity** — a process can be alive but hung with no working connections:
```bash
lsof -i -P | grep python | grep <PID>
```
- **Telegram**: look for an IPv6 connection to `2001:67c:4e8:f004::9:443` (Telegram server)
- **Discord**: look for connections to `gateway-us-east1-b.discord.gg:443` or similar
- If the process has **no network connections** but is alive, it's hung internally — proceed to step 4.

**3. Functional test** — does the gateway actually respond?
```
send_message(action='list')
# If this returns available targets, the gateway is fully functional.
# If it fails or returns empty, proceed to diagnosis.
```

**4. Get a stack trace** — when the process is alive but not serving:
```bash
# macOS: sample the process to see what threads are doing
sample <PID> 3

# Or send Python SIGQUIT for a traceback (may write to stderr/logs):
kill -SIGQUIT <PID>
```

**5. Check the logs directory** — this is a frequent point of failure:
```bash
ls -la ~/.hermes/profiles/<profile>/logs/
```
If the directory is empty or missing, the gateway has been running silently with no crash traces. **Fix:**
```bash
mkdir -p ~/.hermes/profiles/<profile>/logs
kill <PID>   # launchd auto-restarts with logs now enabled
```

**6. Check for system crash reports:**
```bash
log show --predicate 'process == "python3.1"' --last 6h --style compact | grep -i "gateway\|error\|exit\|signal\|killed" | tail -20
ls -lt ~/Library/Logs/DiagnosticReports/ | head -5
```

**7. If the gateway was already replaced by launchd** (old PID is gone, new PID exists):
- The new process may be starting up — wait 10-15 seconds and re-test
- Check if it has established its platform connection (step 2)
- This is normal behavior for launchd-configured gateways with KeepAlive

**8. Gateway log gap analysis** — When the gateway silently crashes with no trace, the gateway.log tells the story through its GAPS:

```bash
tail -100 ~/.hermes/profiles/<profile>/logs/gateway.log
```

What to look for:
- **The last successful message** — did the user's last message get processed before the crash? If yes, the gateway was alive until at least that point.
- **The first line of the new gateway startup** — `INFO gateway.run: Starting Hermes Gateway...` marks the new process
- **The gap between last entry and new startup** — this is the crash window. If it's seconds, the crash was abrupt. If minutes, the process was hung before dying.
- **DNS failure clusters** — look for repeated `[Errno 8] nodename nor servname provided, or not known` errors. These indicate DNS resolver flakiness, not a gateway bug. Multiple retries followed by fallback IP usage is the normal recovery pattern.
- **Network error waves** — `Bad Gateway`, `ReadError`, `Timed out` in sequence = the Telegram API was unreachable for a period. The gateway has built-in reconnect (10 attempts with backoff).

**9. Read the exit diagnostic log** — The gateway writes JSON-structured exit diagnostics to `gateway-exit-diag.log`. Each `gateway.start` entry should have a matching `asyncio.run.returned` + `gateway.exit_nonzero` (for crashes) or clean exit. A `gateway.start` with NO corresponding exit entry means the process was killed ungracefully (SIGKILL, or by another gateway's `--replace` flag):

```bash
tail -20 ~/.hermes/profiles/<profile>/logs/gateway-exit-diag.log
```

Exit patterns:
- `asyncio.run.returned` + `success: false` + `gateway.exit_nonzero` = process exited with error (launchd will restart per KeepAlive)
- `gateway.start` with NO matching exit entry = killed mid-flight (not a clean exit)
- Cascade of rapid `gateway.start` / `asyncio.run.returned` pairs = crash loop (update/config issue)

**10. Check `gateway.error.log` for actual tracebacks** — The `--replace` mechanism sends SIGTERM to the old PID, which may not write an exit diagnostic. But real crashes (unhandled exceptions, segfaults) DO write to `gateway.error.log` and `errors.log`. Search for today's date:

```bash
grep -n "$(date +%F)" ~/.hermes/profiles/<profile>/logs/gateway.error.log
grep -n "$(date +%F)" ~/.hermes/profiles/<profile>/logs/errors.log
```

### Check for dual gateway instances
The gateway checks for other running instances on startup. If you see:
```
ERROR gateway.run: Another gateway instance (PID XXXX) started during our startup.
```
Kill ALL gateway processes, then reload launchctl. Dual instances happen when a stale process outlasts a killed launchd service.

## Monitoring & Health Checks

For long-running gateways (46h+ uptime typical), silent crashes are the most common failure mode — the process vanishes with no trace, and launchd auto-restarts it. A periodic health check catches these gaps.

### Watchdog Pattern (no_agent=True cron)

Use a **no_agent=True cron job** running a shell script. This is the right approach because:
- **Zero LLM cost** — the script runs bare, the agent never fires
- **Silent when healthy** — empty stdout = no message sent to you
- **Alert on failure** — non-empty stdout is delivered verbatim
- **Auto-restore** — the script can trigger launchd recovery

**How to create one:**

1. Write a health-check script to `~/.hermes/profiles/<profile>/scripts/` (or `~/.hermes/scripts/`)
2. Create the cron job with `no_agent=True` and `script=<filename>`

The script should follow this structure:
```bash
#!/bin/bash
# Silent when healthy, noisy when down. Designed for no_agent=True cron.

HERMES_HOME="/Users/greg/.hermes/profiles/johnny"
LOG_DIR="$HERMES_HOME/logs"

# 1. Check process alive
GW_PID=$(pgrep -f "gateway run.*--profile johnny" | head -1)
if [ -z "$GW_PID" ]; then
    echo "⚠️ Gateway DOWN — no process found at $(date)"
    # Attempt restart
    launchctl load ~/Library/LaunchAgents/ai.hermes.gateway-johnny.plist 2>&1
    exit 0
fi

# 2. Check log freshness (sign of life)
GATEWAY_LOG="$LOG_DIR/gateway.log"
if [ -f "$GATEWAY_LOG" ]; then
    NOW=$(date +%s)
    LOG_MTIME=$(stat -f "%m" "$GATEWAY_LOG" 2>/dev/null)
    DIFF=$(( NOW - LOG_MTIME ))
    if [ "$DIFF" -gt 900 ]; then  # no activity in 15 min
        echo "⚠️ Gateway PID $GW_PID alive but log tailed off $(( DIFF / 60 )) min ago"
        tail -5 "$GATEWAY_LOG"
    fi
fi

# Silent exit (no stdout) = healthy
exit 0
```

**Cron job creation:**
```bash
cronjob action=create name=gateway-health-check schedule="every 30m" \
    script=gateway-health-check.sh \
    no_agent=true \
    deliver=telegram
```

**What frequency to use:** 30 min is good for catching crashes within the window. The script stays totally silent when healthy. If you want tighter (15 min) or looser (2h), adjust the schedule — it won't change spam level since healthy runs produce zero output either way.

### What the Watchdog Script Checks

| Check | What | When it alerts |
|-------|------|----------------|
| Process alive | `pgrep -f "gateway run"` | No gateway process found |
| Log freshness | `stat -f "%m" gateway.log` vs `date +%s` | No writes in 15+ minutes (hung process) |
| Auto-restore | `launchctl load` | After detecting a dead process, attempts recovery |

### Possible Pitfalls

- **PATH in cron context** — Cron jobs have a minimal PATH. The health-check script uses absolute paths for everything to avoid this.
- **`stat -f` portability** — `stat -f "%m"` is macOS-specific. On Linux, `stat -c "%Y"` is used instead.
- **Log rotation** — If the gateway.log rotates between checks, `stat` returns the new (small) file's mtime which resets the freshness counter. This is fine — it means the process just rotated its logs.
- **Script path resolution** — The cron system resolves relative script paths under `~/.hermes/profiles/<profile>/scripts/` (or `~/.hermes/scripts/` as fallback). Don't use absolute paths; they'll be rejected with a helpful error message.

## Network Diagnostics: ISP-Level DNS/SSL Failures

Airtel (and other Indian ISPs) can cause intermittent DNS resolution failures that cascade across all external-facing services. When multiple independent services fail simultaneously, suspect the network, not the configuration.

### Symptom Cluster

When an ISP DNS resolver is flaky, you see ALL of these together:
```
# Telegram: DNS failure
[Errno 8] nodename nor servname provided, or not known → Telegram failover IP 149.154.166.110

# Tavily (web_search): SSL handshake timeout
_ssl.c:999: The handshake operation timed out

# web_extract: zero content, SSL timeout
https://news.ycombinator.com/ (no content to process)
```

### Diagnosis Chain

**Step 1 — Correlate timestamps across log files:**
```bash
# Check gateway log for Telegram DNS failures
grep "nodename\|ssl\|Timeout\|ReadError" ~/.hermes/profiles/<profile>/logs/gateway.log

# Check errors log for Tavily/web failures in the same time window
grep "$(date +%F)" ~/.hermes/profiles/<profile>/logs/errors.log | grep -i "ssl\|handshake\|timeout"
```

**Step 2 — Run a multi-target connectivity test:**
```bash
# Test DNS + SSL against multiple independent services
for host in api.telegram.org tavily.io api.openai.com github.com; do
    echo -n "DNS $host: "
    dig +short $host 2>&1 || echo "FAIL"
    echo -n "SSL $host: "
    curl -sI --max-time 5 https://$host 2>&1 | head -1 || echo "FAIL"
done
```

**Step 3 — Check DNS resolver health:**
```bash
# Test with a different DNS resolver
dig @8.8.8.8 api.telegram.org +short
dig @1.1.1.1 api.telegram.org +short
```

### What It Means

- **If Telegram DNS fails + Tavily SSL times out + web_extract gets zero content** in the same time window → **It's the ISP, not the gateway.** Airtel's DNS resolver occasionally drops queries for certain domains, causing cascading failures across all HTTPS services.
- The gateway has built-in reconnect with fallback IPs (10 attempts, exponential backoff). Recovery is automatic once the ISP resolves the issue.
- Cron jobs that depend on web_search/web_extract will produce degraded briefings during these windows. The agent handles this gracefully (works around with local data).

### ClientConnectorDNSError

```
ClientConnectorDNSError: Cannot connect to host gateway-us-east1-b.discord.gg:443 ssl:default [nodename nor servname provided, or not known]
```

Same root cause — DNS resolution failure. Discord reconnection is handled by the gateway's built-in retry loop. Check gateway logs for successful reconnection before assuming the platform is permanently down.

## Channel Discovery

After connecting, use `send_message(action='list')` to see available targets:

```python
send_message(action='list')
# → Available messaging targets:
#   discord:#general-chat
#   discord:#personal-work
#   ...
```

New channels appear automatically after the bot sees them in the server.

## Logs to Check

| Log | Path | What to look for |
|-----|------|-----------------|
| Gateway | `~/.hermes/profiles/<profile>/logs/gateway.log` | Connect/disconnect, unauthorized warnings, message delivery |
| Errors | `~/.hermes/profiles/<profile>/logs/gateway.error.log` | Crashes, stack traces |
| Agent | `~/.hermes/profiles/<profile>/logs/agent.log` | Session-specific tool errors |

## Pitfalls

- **Home directory override in profile terminal** — When running shell commands in the Johnny (or any profile) environment, `HOME` is overridden to a profile-specific internal directory (e.g. `/Users/greg/.hermes/profiles/johnny/home`). This means `~` resolves to THAT path, NOT your actual home (`/Users/greg`). So `~/.hermes/profiles/johnny/logs/gateway.log` becomes `/Users/greg/.hermes/profiles/johnny/home/.hermes/profiles/johnny/logs/gateway.log` — a non-existent path. **Always use absolute paths** (`/Users/greg/.hermes/...`) when investigating logs from inside the profile environment. This is the #1 cause of "logs are empty/not found" false alarms.

- **Profile .env, not main .env** — The single most common mistake...
- **Dual gateway instances** — After a crash loop, multiple gateway processes can exist. Kill ALL of them before starting fresh.
- **Empty logs directory** — The profile `logs/` directory can get emptied or deleted (e.g. during file cleanup or profile migrations). When launchd writes stdout/stderr to a path that doesn't exist, the output is silently dropped. The gateway runs fine but crash traces are lost. **Fix:** `mkdir -p ~/.hermes/profiles/<profile>/logs` and restart.
- **Launched process may have auto-replaced** — Between the time a crash happens and the time you check, launchd may have already spawned a new PID. Don't assume the PID you find is the same one that crashed. Check `lsof -i` for network connectivity to verify the new process is actually connected.
- **Opus codec warning is harmless** — Don't chase this. Text messaging works fine without it.
- **Channel prompts don't control auth** — They control the system prompt per channel. Auth is controlled by env vars only.
- **Bot needs `message_content` intent** enabled in the Discord Developer Portal under Bot → Privileged Gateway Intents — otherwise the bot can't read messages even with a valid token.
- **Slash-command fingerprint sync** — Seeing `Skipping Discord slash command sync: same slash-command fingerprint already synced` is normal and expected.
- **`gateway_state.json` may be stale** — The gateway state file is written on startup and may not reflect live platform status. A platform can be disconnected (DNS crash, token expiry) while the state still shows `"state": "connected"` from the last update. Cross-check with gateway logs.
- **DNS failures cause silent disconnection** — Intermittent DNS resolution failures (e.g. `ClientConnectorDNSError: Cannot connect to host gateway-us-east1-b.discord.gg:443 ssl:default [nodename nor servname provided, or not known]`) cause Discord to disconnect. The gateway reconnection loop may or may not succeed. Check `grep -i "nodename\|dns\|dns_error" <profile>/logs/gateway.error.log` when a platform is online but not delivering.
- **Channel directory can be empty despite connection** — A platform that successfully connects may still show an empty channel list (`discord: []` in `channel_directory.json`). This can happen if the bot hasn't fully synced guilds, has been removed from channels, or the directory was written before channels populated. Use `send_message(action='list')` to check live availability.
