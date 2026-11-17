# Verify Before Handoff — Deployment Quality Standard

Greg gets frustrated — and rightly — when the agent deploys code and asks him to try it without verifying it actually works. A "connected" UI state or a 200 OK response is NOT proof the pipeline works.

## Incidents (reinforcing this rule)

1. **`SmallWebRTCTransport.params()` crash** — WebRTC connected (ICE completed, tracks exchanged), `/start` returned 200, browser showed "connected." But the bot subprocess crashed with `AttributeError: type object 'SmallWebRTCTransport' has no attribute 'params'`. Greg heard silence. Agent had not checked logs.

2. **`ElevenLabsTTSSettings` crash** — Same silent failure pattern. `TypeError: ElevenLabsTTSSettings.__init__() got an unexpected keyword argument 'output_format'`. Again, WebRTC "connected" but pipeline dead. Agent deployed a fix for #1, asked Greg to try, and #2 was still broken.

## Rule

Before asking Greg to test anything, run a verification sequence on the server:
- Validate constructors work (import + Settings test)
- Hit the endpoint and check for backend errors in logs
- Confirm the pipeline initializes without tracebacks

## Verification sequence (example)

```bash
# 1. Constructor validation
ssh server ".venv/bin/python -c 'import bot; ...'"

# 2. Start session + check logs
curl -s http://server:port/start -X POST -d '{...}'
sleep 2
ssh server "grep -a 'ERROR|TypeError|AttributeError' /var/log/*.log | grep -v 'expected_errors'"

# 3. Must return empty
```

## What to say when you genuinely can't verify

"If there's still silence, check the browser console (F12) and I'll check server logs on my end." — not "Try it now, it should work."

## Relationship to other preferences

This is distinct from "Action-First" — the action here IS verifying, not skipping verification to be fast. It aligns with "Context Before Action" — the context needed before handoff is: did the thing actually work?
