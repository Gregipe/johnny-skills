# ARA Server launchd Configuration

Actual plist at `~/Library/LaunchAgents/com.ara.server.plist` — auto-start on login + auto-restart on crash.

## plist

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ara.server</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/greg/ara/venv/bin/python</string>
        <string>-u</string>
        <string>/Users/greg/ara/server.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/greg/ara</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>ThrottleInterval</key>
    <integer>5</integer>

    <key>StandardOutPath</key>
    <string>/Users/greg/ara/logs/server.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/greg/ara/logs/server-err.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/greg/ara/venv/bin:/Users/greg/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

## Paths

| Item | Path |
|------|------|
| plist | `~/Library/LaunchAgents/com.ara.server.plist` |
| stdout log | `/Users/greg/ara/logs/server.log` |
| stderr log | `/Users/greg/ara/logs/server-err.log` |
| project | `/Users/greg/ara/` |

## Commands

```bash
# Load on current session
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ara.server.plist

# Unload
launchctl bootout gui/$(id -u)/com.ara.server

# Check status
launchctl print gui/$(id -u)/com.ara.server

# Hot-reload after plist edit
launchctl bootout gui/$(id -u)/com.ara.server 2>/dev/null
sleep 1
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ara.server.plist
```

## History

Created 2026-06-04 after ARA server kept getting killed by macOS memory pressure (exit code 137). launchd restarts it within 5 seconds automatically.
