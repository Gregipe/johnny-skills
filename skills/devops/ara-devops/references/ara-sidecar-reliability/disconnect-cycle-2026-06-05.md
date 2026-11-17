# Disconnect Cycle — 2026-06-05

After ~7 hours of runtime following the watchdog + port-kill + health-check fix deployment, the watchdog logged:

## Timeline

| Time | Watchdog Action | Type |
|------|-----------------|------|
| 08:19 | Sidecar started clean | Startup |
| 09:33 | State=disconnected | Disconnect |
| 09:36 | Reconnected | Self-heal |
| 12:04 | Process died (exit 1) | Crash |
| 12:04 | Restarted (PID 98425) | Restart |
| 12:22 | State=disconnected | Disconnect |
| 12:53 | Reconnected | Self-heal |
| 14:49 | State=disconnected | Disconnect |
| 15:18 | State=connecting | Reconnect attempt |
| 15:19 | Reconnected | Self-heal |
| 15:23 | Process died (exit -9, manual kill) | Manual |

## Key Observations

1. **Disconnects are normal** — WhatsApp WebSocket drops every few hours. Baileys self-heals via `connection.update` → `shouldReconnect` → 5s reconnect timer in most cases.
2. **Process crashes are rare** — Only 1 unexplained crash (exit code 1, no visible error because logs went to DEVNULL at that time). The watchdog caught it within 60s.
3. **Zombie state is the real threat** — After the 12:04 crash + restart, the sidecar reported `connected=true` but had 314 "failed to decrypt" errors. All incoming messages were silently dropped for ~3 minutes until the user noticed. This was the motivation for adding `decryptErrorCount` tracking.

## After Zombie Detection Deployed

After the `decryptErrorCount` + watchdog check was deployed at ~15:30, further runtime showed zero decrypt error spikes. The watchdog caught one more disconnect (15:48) that self-healed within the same 60s cycle.
