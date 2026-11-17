# Gateway Recovery — Error Transcripts & Patterns

Collected from session May 2026. These are specific error strings that signal a gateway needs recovery.

## 1. Zombie PID Blocking Restart

The old PID stays alive but unresponsive. Launchd won't restart because it sees the process.

**Log evidence:**
```
Gateway service is loaded
"PID" = 60137;
```
But process hasn't logged anything in hours. `hermes gateway status` shows it as running but Telegram doesn't respond.

**Shell evidence of zombie restart scripts:**
```
greg   60137  ...  /venv/bin/python -m hermes_cli.main gateway run --replace   (old, hung)
greg   9215   ...  bash -lc while kill -0 60137 2>/dev/null; do sleep 0.2; done; hermes gateway restart
greg   60113  ...  /venv/bin/python3 /venv/bin/hermes gateway restart
greg   60114  ...  launchctl kickstart -k gui/501/ai.hermes.gateway
```

**Fix:** Kill ALL of these, then `hermes gateway start`.

## 2. Network Retry Exhaustion

Gateway attempts 10 reconnects, then gives up.

**Log evidence:**
```
WARNING gateway.platforms.telegram: [Telegram] Telegram network error (attempt 9/10), reconnecting in 60s. Error: Timed out
WARNING gateway.platforms.telegram_network: [Telegram] Fallback IP 149.154.167.220 failed
WARNING gateway.platforms.telegram: [Telegram] Telegram polling reconnect failed: Timed out
WARNING gateway.platforms.telegram: [Telegram] Telegram network error (attempt 10/10), reconnecting in 60s. Error: Timed out
ERROR gateway.platforms.telegram: [Telegram] Telegram polling could not reconnect after 10 network error retries. Restarting gateway.
ERROR gateway.run: Fatal telegram adapter error (telegram_network_error): ...
ERROR gateway.run: All messaging platforms failed with retryable errors. Shutting down gateway for service restart
INFO gateway.run: Gateway stopped
ERROR gateway.run: Gateway exiting with failure: Telegram polling could not reconnect after 10 network error retries.
```

**Root cause:** Airtel ISP peering to Telegram's API servers (api.telegram.org) drops intermittently. Primary IP 149.154.166.110 and fallback 149.154.167.220 both fail during these windows. IPv6 route (2001:67c:4e8:f004::9) is more stable.

**Mitigation:** Increase `MAX_NETWORK_RETRIES = 10` in `gateway/platforms/telegram.py` line 472. Or wait for Airtel routing to recover and restart manually.

## 3. Gateway Drain Timeout During Restart

When restarting with active agents, the gateway waits 180s before force-interrupting.

**Log evidence:**
```
INFO gateway.run: Stopping gateway for restart...
WARNING gateway.run: Gateway drain timed out after 180.0s with 1 active agent(s); interrupting remaining work.
INFO gateway.platforms.base: [Telegram] Sending response (64 chars) to 557413154
INFO gateway.platforms.telegram: [Telegram] Disconnected from Telegram
INFO gateway.run: Skipping .clean_shutdown marker — drain timed out with interrupted agents
```

**Fix:** Kill the old gateway PID manually (`kill -9`) and start fresh.

## 4. Stale-Code Self-Check (After `hermes update`)

After updating Hermes (`hermes update`), the running gateway detects that source files are newer than its boot time and requests a graceful restart.

**Log evidence:**
```
WARNING gateway.run: Stale-code self-check: source files newer than gateway boot time (boot=1777714156, newest=1778903686) — requesting graceful restart.
```

**Pitfall: `hermes gateway restart` may hang.** The restart command tries to gracefully drain the old gateway first, but the stale-code check may already be mid-cycle. The command can block indefinitely:

```
hermes gateway restart  # hangs, eventually times out
```

**Fix:** Kill the old gateway PID first, then start fresh:

```bash
ps aux | grep 'gateway run' | grep -v grep | awk '{print $2}' | xargs kill -9
sleep 2
hermes gateway start
```

**Confirmation:** Check logs for `✓ telegram connected`:
```bash
tail -5 ~/.hermes/logs/gateway.log
```

**Root cause:** `hermes gateway restart` uses launchd's `kickstart -k` which sends SIGTERM and waits for the PID to die. If the process doesn't die quickly (stuck in a drain/retry cycle), the wait blocks. Always prefer `kill -9` + `hermes gateway start` over `hermes gateway restart` after updates.

## 5. Profile `.env` Gap — Tokens in Wrong `.env`

When running under a named profile, the gateway loads `.env` from `{HERMES_HOME}/.env` — which resolves to the **profile's** `.env` (`~/.hermes/profiles/<name>/.env`), NOT the global `~/.hermes/.env`. Tokens added to the global `.env` are invisible to the profile gateway.

**Log evidence:**
```
ERROR gateway.platforms.discord: [Discord] No bot token configured
WARNING gateway.run: ✗ discord failed to connect
```
Yet `grep DISCORD_BOT_TOKEN ~/.hermes/.env` shows the token exists — because it's in the global `.env`, not the profile's.

**Root cause:** `get_hermes_home()` returns the profile directory when a profile is active. `load_hermes_dotenv()` loads `.env` relative to that path. The global `~/.hermes/.env` is never consulted.

**Verify:**
```bash
# Check which .env the profile actually loads
source /path/to/hermes-venv/bin/activate
python3 -c "
from hermes_cli.env_loader import load_hermes_dotenv
from hermes_constants import get_hermes_home
h = get_hermes_home()
print(f'hermes_home: {h}')
print(f'.env used: {h / \".env\"}')
load_hermes_dotenv(hermes_home=h)
import os
print('DISCORD_BOT_TOKEN:', 'SET' if os.getenv('DISCORD_BOT_TOKEN') else 'NOT FOUND')
"

# Quick check without Python
diff <(grep -i "discord" ~/.hermes/.env) <(grep -i "discord" ~/.hermes/profiles/johnny/.env)
```

**Fix:** Copy (or symlink) the missing env var to the profile's `.env`:
```bash
# Find what's missing
grep -v "^#" ~/.hermes/.env | grep -v "^$" > /tmp/global_env_vars.txt
while IFS='=' read -r key val; do
  if ! grep -q "^${key}=" ~/.hermes/profiles/johnny/.env 2>/dev/null; then
    echo "MISSING: ${key}"
  fi
done < /tmp/global_env_vars.txt

# Add a specific missing token
echo "DISCORD_BOT_TOKEN=<value>" >> ~/.hermes/profiles/johnny/.env
```

**Prevention:** After adding any new platform token to the global `.env`, always mirror it into each profile's `.env` that needs it. Or run `hermes gateway setup` from within the profile context.

## 6. Double Gateway Instance Conflict

When both a default launchd service (`ai.hermes.gateway`, no profile) and a profile-specific service (`ai.hermes.gateway-<name>`) are registered, they fight each other, creating a restart loop.

**Log evidence:**
```
WARNING gateway.run: Shutdown context: signal=SIGTERM under_systemd=yes parent_pid=1 ...
ERROR  gateway.run: Another gateway instance (PID 97206) started during our startup. Exiting to avoid double-running.
WARNING gateway.run: Shutdown context: signal=SIGTERM under_systemd=yes ...
```
Repeats indefinitely. Telegram reconnects briefly between cycles but never stays up.

**Root cause:** Two launchd plist files exist:
- `~/Library/LaunchAgents/ai.hermes.gateway.plist` — default, no profile
- `~/Library/LaunchAgents/ai.hermes.gateway-<name>.plist` — profile-specific

When both are loaded (`launchctl list | grep hermes`), launchd starts them independently. Each instance sees the other's PID file and exits.

**Fix:**
```bash
# 1. Unload the duplicate (non-profile) service
launchctl bootout gui/$(id -u)/ai.hermes.gateway

# 2. Remove its plist so it doesn't auto-load on reboot
mv ~/Library/LaunchAgents/ai.hermes.gateway.plist /tmp/

# 3. Kill all gateway processes
kill -9 $(ps aux | grep 'gateway.*run' | grep -v grep | awk '{print $2}') 2>/dev/null

# 4. Clean stale PID/lock files
rm -f ~/.hermes/profiles/<name>/gateway.pid ~/.hermes/profiles/<name>/gateway.lock

# 5. Restart the profile service
hermes gateway start

# 6. Verify
launchctl list | grep hermes   # should show only the -<name> service
```

**Detection:** Use `launchctl list | grep hermes` to see all registered gateway services. If you see both `ai.hermes.gateway` and `ai.hermes.gateway-<name>`, you have the conflict.

**Prevention:** Always start the gateway with `hermes gateway start` (uses profile context when a profile is active). Manually or accidentally running `hermes gateway run ...` without the profile flag can register a second service.

## 7. Unauthorized User — Platform Connected but User Blocked

The bot is online and connected to the platform (Discord, Telegram, etc.), but messages from a specific user are silently dropped or logged as "Unauthorized." The user sees the bot online but gets no response.

**Log evidence:**
```
WARNING gateway.run: Unauthorized user: 1002523983352180756 (GregIpe) on discord
```

No other errors — the platform adapter connected successfully (`✓ discord connected`, `Connected as Hermes Bot HQ#2854`), but every message from that user triggers an authorization rejection at the gateway level.

**Root cause:** The gateway's `_is_user_authorized()` method checks the `{PLATFORM}_ALLOWED_USERS` environment variable for each platform. If this env var is empty or not set, the default is **deny**. The mechanism is defined in `gateway/run.py` as a `platform_env_map`:

| Platform | Env var |
|----------|---------|
| Discord | `DISCORD_ALLOWED_USERS` |
| Telegram | `TELEGRAM_ALLOWED_USERS` |
| WhatsApp | `WHATSAPP_ALLOWED_USERS` |
| Slack | `SLACK_ALLOWED_USERS` |
| Signal | `SIGNAL_ALLOWED_USERS` |
| Mattermost | `MATTERMOST_ALLOWED_USERS` |
| Matrix | `MATRIX_ALLOWED_USERS` |
| Email | `EMAIL_ALLOWED_USERS` |
| SMS | `SMS_ALLOWED_USERS` |
| DingTalk | `DINGTALK_ALLOWED_USERS` |
| Feishu | `FEISHU_ALLOWED_USERS` |
| WeCom | `WECOM_ALLOWED_USERS` |
| BlueBubbles | `BLUEBUBBLES_ALLOWED_USERS` |
| QQ Bot | `QQ_ALLOWED_USERS` |
| Yuanbao | `YUANBAO_ALLOWED_USERS` |

Each platform also has an `{PLATFORM}_ALLOW_ALL_USERS` flag (e.g. `DISCORD_ALLOW_ALL_USERS=true`) to bypass the allowlist entirely.

The Discord adapter (`gateway/platforms/discord.py`) has its own parallel authorization layer that also reads `DISCORD_ALLOWED_USERS` and `DISCORD_ALLOWED_ROLES` (comma-separated role IDs). When both `DISCORD_ALLOWED_USERS` and `DISCORD_ALLOWED_ROLES` are empty in the adapter, it falls back to "everyone is allowed" — but the gateway's `_is_user_authorized()` in `run.py` still checks *its own* env var and defaults to deny.

**Fix — add the user's platform ID to the profile's `.env`:**

```bash
# Find the user's platform ID from the "Unauthorized user" warning in the logs
# Example: "Unauthorized user: 1002523983352180756 (GregIpe) on discord"
# The first number is the user's Discord user ID

# Add it to the profile's .env (not the global one — see Pattern 5 above)
echo "DISCORD_ALLOWED_USERS=1002523983352180756" >> ~/.hermes/profiles/<name>/.env

# For multiple users, comma-separate:
echo "DISCORD_ALLOWED_USERS=1002523983352180756,9876543210987654" >> ~/.hermes/profiles/<name>/.env

# To allow ALL users (less secure):
echo "DISCORD_ALLOW_ALL_USERS=true" >> ~/.hermes/profiles/<name>/.env
```

**After adding the env var, the gateway must be restarted** — env vars are read at startup and are not live-reloaded:

```bash
# Kill the old gateway and let launchd restart it
ps aux | grep 'gateway run' | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
sleep 2

# If using launchd:
launchctl load ~/Library/LaunchAgents/ai.hermes.gateway-<name>.plist 2>/dev/null

# Or start via CLI:
hermes gateway start

# Verify in logs:
tail -10 ~/.hermes/profiles/<name>/logs/gateway.log
# Look for: ✓ discord connected
# Confirm no new "Unauthorized user" warnings for that user ID
```

**Detection checklist:**

1. Is the bot online on the platform? Check `✓ <platform> connected` in gateway logs.
2. Are there `Unauthorized user: <id> (<name>) on <platform>` warnings?
3. Is `{PLATFORM}_ALLOWED_USERS` set in the profile's `.env`?
4. Was the gateway restarted after adding the env var?

**Cross-platform note:** This pattern affects ALL platforms with authorization support, not just Discord. The same mechanism applies to Telegram, Slack, Signal, and every platform in the table above. If a user reports "the bot is online but doesn't respond to me on platform X," always check the corresponding `{PLATFORM}_ALLOWED_USERS` env var first.

**Discord-specific nuance:** The Discord adapter also supports `DISCORD_ALLOWED_ROLES` (comma-separated role IDs). Users with any of these roles are allowed. If you prefer role-based authorization:
```bash
echo "DISCORD_ALLOWED_ROLES=123456789012345678,987654321098765432" >> ~/.hermes/profiles/<name>/.env
```
Note: This requires the `members` privileged intent enabled in the Discord Developer Portal.
