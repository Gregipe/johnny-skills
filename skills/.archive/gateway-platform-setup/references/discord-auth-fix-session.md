# Discord Auth Fix — Session Reference (May 16, 2026)

## Problem
Discord bot showed as online (connected as "Hermes Bot HQ#2854") but Greg's messages were silently dropped. Gateway logs showed:
```
WARNING gateway.run: Unauthorized user: 1002523983352180756 (GregIpe) on discord
```

## Root Cause
The gateway uses `DISCORD_ALLOWED_USERS` env var as an allowlist. The profile `.env` had `DISCORD_BOT_TOKEN` set but **no `DISCORD_ALLOWED_USERS`**. When the env var is unset, the gateway denies ALL users by default.

## Fix
1. Added to `~/.hermes/profiles/johnny/.env`:
   ```
   DISCORD_ALLOWED_USERS=1002523983352180756
   ```
   (Added right after the `DISCORD_BOT_TOKEN` line)

2. Restarted the gateway:
   ```bash
   kill <PID>
   # Launchctl auto-restarted it.
   # If not: launchctl load ~/Library/LaunchAgents/ai.hermes.gateway-johnny.plist
   ```

3. Verified:
   - `ps aux | grep 'gateway run'` → new PID
   - `tail -5 ~/.hermes/profiles/johnny/logs/gateway.log` → "Connected as Hermes Bot HQ#2854" with no "Unauthorized" warnings
   - `send_message(action='list')` → `#morning-briefing` channel visible
   - Test message sent to `discord:#personal-work` → delivered

## User Info
- Discord User ID: 1002523983352180756
- Discord Username: GregIpe
- Server: Hermes HQ
