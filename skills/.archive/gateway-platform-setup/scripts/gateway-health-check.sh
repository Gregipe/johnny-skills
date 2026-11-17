#!/bin/bash
# Gateway health check watchdog — silent when healthy, noisy when down.
# Designed for no_agent=True cron usage (stdout → delivery).
#
# Usage in cron: cronjob action=create name=gateway-health-check \
#     schedule="every 30m" script=gateway-health-check.sh \
#     no_agent=true deliver=telegram
#
# Configuration — change these for your profile:
HERMES_HOME="/Users/greg/.hermes/profiles/johnny"
GATEWAY_PLIST="$HOME/Library/LaunchAgents/ai.hermes.gateway-johnny.plist"
PROFILE_NAME="johnny"
LOG_DIR="$HERMES_HOME/logs"
NOW=$(date +%s)

# 1. Check if gateway process is running
GW_PID=$(pgrep -f "gateway run.*--profile $PROFILE_NAME" | head -1)

if [ -z "$GW_PID" ]; then
    echo "⚠️  Gateway DOWN — no process found at $(date)"
    echo "Attempting restart via launchctl..."
    launchctl load "$GATEWAY_PLIST" 2>&1
    sleep 5
    GW_PID=$(pgrep -f "gateway run.*--profile $PROFILE_NAME" | head -1)
    if [ -n "$GW_PID" ]; then
        echo "✅ Restart succeeded (PID $GW_PID)"
    else
        echo "❌ Restart failed — manual intervention needed"
        echo "   Run: hermes --profile $PROFILE_NAME gateway run --replace"
    fi
    exit 0
fi

# 2. Check if log files have recent activity (sign of life)
GATEWAY_LOG="$LOG_DIR/gateway.log"
if [ -f "$GATEWAY_LOG" ]; then
    LOG_MTIME=$(stat -f "%m" "$GATEWAY_LOG" 2>/dev/null)
    DIFF=$(( NOW - LOG_MTIME ))
    if [ "$DIFF" -gt 900 ]; then  # No activity in 15 min
        echo "⚠️  Gateway PID $GW_PID is alive but log tailed off $(( DIFF / 60 )) min ago"
        echo "   Log: $GATEWAY_LOG"
        echo "   Last 5 lines:"
        tail -5 "$GATEWAY_LOG"
    fi
else
    echo "⚠️  No gateway.log found at $GATEWAY_LOG"
fi

# 3. Quick activity check — has Telegram responded recently?
RECENT_TELEGRAM=$(grep -c "Telegram polling resumed\|inbound message.*telegram" "$GATEWAY_LOG" 2>/dev/null)
if [ "$RECENT_TELEGRAM" -eq 0 ]; then
    echo "⚠️  No Telegram activity detected since last log rotation"
fi

# Silent exit (no stdout) = healthy
exit 0
