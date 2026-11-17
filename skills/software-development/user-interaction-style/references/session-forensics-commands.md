# Session Termination Forensics — Command Reference

Concrete commands for diagnosing why a Hermes session ended. Used in Phase 3 of the Session Resumption Protocol.

## Probe the Agent Log

```bash
# Get last activity of a specific session
grep "SESSION_ID" "$HERMES_HOME/logs/agent.log" | tail

# Find the session's last API call + cleanup
grep "SESSION_ID" "$HERMES_HOME/logs/agent.log" | grep -E "API call|Shutting down|Cleaned|Turn ended" | tail

# Trace what happened in the gap between sessions
# Find the line number of last session activity
LAST_LINE=$(grep -n "SESSION_ID" "$HERMES_HOME/logs/agent.log" | tail -1 | cut -d: -f1)
# Then sed from there to next session
sed -n "${LAST_LINE},+50p" "$HERMES_HOME/logs/agent.log"
```

## Check TUI Crash Log

```bash
# List all SIGTERM events with timestamps
grep "=== SIGTERM received" "$HERMES_HOME/logs/tui_gateway_crash.log"

# Count them — 10+ entries over a week is normal for a TUI user
grep -c "=== SIGTERM received" "$HERMES_HOME/logs/tui_gateway_crash.log"

# Check if there's a Python traceback (means real crash, not normal close)
grep -c "Traceback" "$HERMES_HOME/logs/tui_gateway_crash.log"
# If > 0, read that crash entry to find the actual error
```

## Check Errors Log for a Session

```bash
grep "SESSION_ID" "$HERMES_HOME/logs/errors.log" | tail
# WARNING = tool errors (expected in normal operation)
# ERROR = unhandled exceptions (real problems)
```

## Gateway Status

```bash
# Is the gateway process still alive?
ps aux | grep "hermes.*gateway" | grep -v grep

# Check gateway state
cat "$HERMES_HOME/gateway_state.json"

# Gateway log for message timing
ls -lt "$HERMES_HOME/logs/gateway.log"
```

## Process Registry

```bash
# Check for orphaned background processes
cat "$HERMES_HOME/processes.json"
```

## Session DB Queries

```bash
# Get user messages from a session
sqlite3 "$HERMES_HOME/state.db" "SELECT role, substr(content, 1, 500) FROM messages WHERE session_id='SESSION_ID' AND role IN ('user', 'assistant') ORDER BY timestamp;"

# Count messages in a session
sqlite3 "$HERMES_HOME/state.db" "SELECT COUNT(*), MAX(role) FROM messages WHERE session_id='SESSION_ID';"
```

## Common Patterns

| Observation | Diagnosis |
|-------------|-----------|
| SIGTERM entry + cleanup line in agent.log | Normal TUI close |
| SIGTERM entry, no cleanup in agent.log | Hard kill (kill -9, power loss) |
| Traceback in crash log | Gateway code bug |
| agent.log stops mid-API-call | Process killed externally |
| agent.log has "conversation turn" but no "API call" after | Initial system prompt only — user closed before first response |
| 90s+ gap between sessions with no SIGTERM | MacBook sleep — gateway was blocked |
