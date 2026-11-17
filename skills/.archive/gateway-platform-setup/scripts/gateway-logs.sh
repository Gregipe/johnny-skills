#!/bin/bash
# Quick gateway log access — run from ~/.hermes/profiles/<profile>/
# Usage: ./scripts/gateway-logs.sh [tail|error|gwerr|diag|ls|agent]

LOGDIR="/Users/greg/.hermes/profiles/johnny/logs"

case "${1:-}" in
  tail|t)   tail -50 "$LOGDIR/gateway.log" ;;
  error|e)  tail -50 "$LOGDIR/errors.log" ;;
  gwerr|ge) tail -50 "$LOGDIR/gateway.error.log" ;;
  diag|d)   tail -20 "$LOGDIR/gateway-exit-diag.log" ;;
  ls|l)     ls -lh "$LOGDIR/" ;;
  agent|a)  tail -50 "$LOGDIR/agent.log" ;;
  *)        echo "Usage: gateway-logs.sh [tail|error|gwerr|diag|ls|agent]"
            echo ""
            echo "  tail  (t)   - Last 50 lines of gateway.log"
            echo "  error (e)   - Last 50 lines of errors.log"
            echo "  gwerr (ge)  - Last 50 lines of gateway.error.log"
            echo "  diag  (d)   - Last 20 lines of gateway-exit-diag.log"
            echo "  ls    (l)   - List all log files with sizes"
            echo "  agent (a)   - Last 50 lines of agent.log"
            ;;
esac
