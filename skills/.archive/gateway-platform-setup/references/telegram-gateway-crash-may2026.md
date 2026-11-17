# Telegram Gateway Crash — Session Reference (May 19-20, 2026)

## Symptom
Telegram bot unresponsive. User said "it went down" then "John you there?" went through but couldn't be sure.

## Timeline from Gateway Logs

| Time (IST) | Event | Source |
|------------|-------|--------|
| May 19 06:41 | Telegram "Bad Gateway" → reconnected | gateway.log |
| May 19 16:17-16:19 | **DNS failure cluster** — 8 retries of `[Errno 8] nodename nor servname provided, or not known` → fell back to IP 149.154.166.110 → recovered | gateway.log |
| May 19 19:18 | `httpx.ReadError` → attempt 1 → recovered | gateway.log |
| May 19 19:53 | Reconnect timed out → attempt 2 → recovered at 19:54 | gateway.log |
| May 20 06:17:28 | User message "John you there?" **processed normally** by old gateway | gateway.log |
| May 20 06:17:50 | Discord reconnected (normal periodic reconnect) | gateway.log |
| May 20 06:22:21 | **New gateway started** (PID 54974) — old PID 38579 gone | gateway.log + exit-diag |
| May 20 06:22:22 | Telegram connected on new gateway | gateway.log |
| May 20 06:22:36 | Discord connected on new gateway | gateway.log |

**Crash window:** ~4.5 minutes (06:17:50 to 06:22:21). Old process was alive at 06:17, dead by 06:22.

## Investigation Steps (actual sequence)

### 1. Process check
```bash
ps aux | grep "gateway run" | grep -v grep
```
Found PID 38579 (started Mon 8AM, ~46h uptime) — appeared alive.

### 2. Network connectivity check
```bash
lsof -i -P | grep python | grep 38579
```
**No active connections** — process was alive but hung internally (no Telegram/Discord sockets).

### 3. Health check
```bash
curl -s http://localhost:8233/health
```
000 — not responding. No HTTP server on the expected port.

### 4. Stack trace attempt
```bash
sample 38579 3
```
All threads returned `sample_remote_thread_with_frame_filter failed to get thread state` — process unresponsive even to sampling.

### 5. Kill old process
```bash
kill 38579  # returned "No such process"
```
Process had died between check and kill. Launchd auto-restarted PID 54974.

### 6. New gateway verification
```bash
lsof -i -P | grep python | grep 54974
# Found IPv6 connection to 2001:67c:4e8:f004::9:443 = Telegram
send_message(action='list') → returned targets
send_message(target='telegram', message='test') → delivered
```

## What the Exit Diagnostic Log Told Us

The gateway writes `gateway-exit-diag.log` with JSON-structured lifecycle events:

```json
{"ts": "2026-05-18T03:06:03+00:00", "tag": "gateway.start", "pid": 38579}
```

For PID 38579, there was **no** matching:
- `asyncio.run.returned` (success/failure)
- `gateway.exit_nonzero` (non-zero exit)
- `atexit.hook` (cleanup)

This means the process was killed ungracefully — didn't get a clean shutdown signal (SIGTERM from `--replace`) or was SIGKILL'd.

For PID 54974, there was a matching entry at `2026-05-20T00:52:21+00:00`.

## Root Cause

**Silent Python process death after ~46 hours.** Multiple contributing factors:

1. **DNS flakiness** — 8 consecutive DNS resolution failures at 16:17 (ISP issue). The gateway recovered via fallback IP, but the aiohttp event loop may have accumulated stale connections or leaked file descriptors.
2. **1-2 network error waves** (Bad Gateway at 06:41, ReadError at 19:18, Timeout at 19:53) — each recovery consumes internal retry state that async frameworks don't always clean up perfectly.
3. **No crash report** — No macOS crash report, no Python traceback, no core dump. The process vanished between one check and the next.

**Most likely:** An unhandled exception in an async callback deep inside the Telegram polling loop that wasn't caught by the gateway's top-level error handler. In aiohttp-based apps, connection timeouts can trigger exception cascades in the event loop that Python's `asyncio.run()` doesn't surface.

## The `~` Path Resolution Trap

**This was the most confusing part of the diagnosis.** In the Johnny profile's terminal environment, `HOME` is set to `/Users/greg/.hermes/profiles/johnny/home` (not `/Users/greg`). This means:

```bash
# What I typed:
ls -la ~/.hermes/profiles/johnny/logs/
# What actually resolved:
ls -la /Users/greg/.hermes/profiles/johnny/home/.hermes/profiles/johnny/logs/
# → "total 0" (directory didn't exist there)
```

**The actual logs were here** — full and healthy:
```
/Users/greg/.hermes/profiles/johnny/logs/
├── agent.log              (3,779 lines — 535KB, last written 06:28)
├── agent.log.1            (133K, rotated)
├── agent.log.2            (17K)
├── agent.log.3            (5.2MB, oldest)
├── errors.log             (1.3MB)
├── gateway.log            (38,839 lines — 3.6MB)
├── gateway.error.log      (718KB)
├── gateway-exit-diag.log  (1.3MB — 3,967 lines of JSON lifecycle events)
├── gateway-shutdown-diag.log
└── tui_gateway_crash.log
```

**Fix for future: always use absolute paths** when investigating logs from inside this environment.

## Launchd Plist Config

```xml
<key>RunAtLoad</key>     <true/>   <!-- starts on login -->
<key>KeepAlive</key>
<dict>
    <key>SuccessfulExit</key> <false/>   <!-- restart on ANY non-zero exit -->
</dict>
<key>StandardOutPath</key>
    <string>/Users/greg/.hermes/profiles/johnny/logs/gateway.log</string>
<key>StandardErrorPath</key>
    <string>/Users/greg/.hermes/profiles/johnny/logs/gateway.error.log</string>
```

Note: `SuccessfulExit: false` means restart on crash (non-zero exit), but NOT on clean exit (code 0). This is correct — the gateway should stay dead if it exits cleanly (e.g. intentional stop).

## Log Access Script Created

```bash
~/.hermes/profiles/johnny/scripts/gateway-logs.sh [tail|error|gwerr|diag|ls|agent]
```

Usage: `bash ~/.hermes/profiles/johnny/scripts/gateway-logs.sh tail` etc.

## Diagnostic Signal Reference

| Signal | What It Means |
|--------|---------------|
| Old PID gone, new PID exists | Launchd auto-restarted after crash |
| `ps` shows alive but `lsof -i` has no connections | Process hung internally |
| IPv6 to `2001:67c:4e8:f004::9:443` | Telegram connected |
| `[Errno 8] nodename nor servname` in logs | DNS resolver flaky (ISP side) |
| No exit diagnostic for old PID | Killed ungracefully (SIGTERM/SIGKILL) |
| `~` resolves wrong path | `HOME` overridden by profile — use absolute paths |
