---
name: macos-launchd-service
description: >-
  Create, load, and debug launchd plists for auto-starting and auto-restarting
  long-running services (Python servers, Node processes, daemons) on macOS.
  Covers plist format, PATH/environment pitfalls, bootout/bootstrap lifecycle,
  log management, and crash-recovery patterns.
---

# macOS launchd Service Management

Create resilient, crash-recovering services on macOS using native launchd.

## Trigger

- User wants to auto-start a server on login
- User wants a service to auto-restart when it crashes
- Exit code 137 (SIGKILL) keeps killing a server under memory pressure
- Any "run this forever on macOS" problem

## Anatomy of a LaunchAgent plist

Place at `~/Library/LaunchAgents/<name>.plist` (user-level, starts on login):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.yourservice.name</string>

    <key>ProgramArguments</key>
    <array>
        <string>/path/to/executable</string>
        <string>-flag</string>
        <string>/path/to/script.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/path/to/project</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>ThrottleInterval</key>
    <integer>5</integer>

    <key>StandardOutPath</key>
    <string>/path/to/logs/stdout.log</string>

    <key>StandardErrorPath</key>
    <string>/path/to/logs/stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/path/to/venv/bin:/Users/username/.local/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

## Key Config Options

| Key | Purpose |
|-----|---------|
| `KeepAlive` | Auto-restart on crash (set to `<true/>`) |
| `ThrottleInterval` | Min seconds before restart (prevents restart loops) |
| `RunAtLoad` | Start immediately when loaded |
| `EnvironmentVariables` | **Critical** — launchd has a bare-minimum PATH by default |

## The PATH Trap (most common failure)

launchd runs with PATH=`/usr/bin:/bin`. That means `node`, `brew`, and everything in `~/.local/bin` or `/opt/homebrew/bin` **won't be found** unless you explicitly set them:

```xml
<key>EnvironmentVariables</key>
<dict>
    <key>PATH</key>
    <string>/Users/greg/ara/venv/bin:/Users/greg/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
</dict>
```

## Lifecycle Commands

```bash
# Load and start
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.service.plist

# Unload and stop
launchctl bootout gui/$(id -u)/com.service.name

# Check if running
launchctl print gui/$(id -u)/com.service.name

# List all user agents
launchctl list | grep com.yourservice
```

**Always use `bootstrap`/`bootout`** on modern macOS. The legacy `load`/`unload` still works but is deprecated.

## Hot-Reload (update plist without reboot)

```bash
launchctl bootout gui/$(id -u)/com.service.name 2>/dev/null
sleep 1
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.service.plist
```

## Debugging

```bash
# Check logs
cat /path/to/logs/stderr.log

# Check process
lsof -i :PORT

# Verify it's actually serving requests
curl -s -o /dev/null -w "%{http_code}" http://localhost:PORT/endpoint

# Check launchd's view of the job
launchctl print gui/$(id -u)/com.service.name
```

## Patterns

### KeepAlive + ThrottleInterval (crash recovery)
```xml
<key>KeepAlive</key>
<true/>
<key>ThrottleInterval</key>
<integer>5</integer>
```
The server comes back within seconds of any crash, but won't restart-loop if it dies faster than every 5 seconds.

### Python virtualenv
Use the venv's interpreter directly, not the system python:
```xml
<array>
    <string>/path/to/venv/bin/python</string>
    <string>-u</string>
    <string>/path/to/project/server.py</string>
</array>
```
The `-u` flag disables stdout buffering so logs appear immediately.

## Verification Checklist

- [ ] `lsof -i :PORT` shows process listening
- [ ] `curl` to endpoint returns 200
- [ ] `launchctl print gui/$(id -u)/com.service.name` shows `state = running`
- [ ] Log files are being written (check `tail -f`)
- [ ] No "command not found" errors in stderr (PATH check)
- [ ] Kill the process with `kill -9` and verify it restarts within ThrottleInterval seconds
