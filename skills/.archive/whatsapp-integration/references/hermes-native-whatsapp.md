# Hermes-Native WhatsApp Gateway (Johnny, since Oct 2026)

Greg's current WhatsApp = Hermes's own gateway adapter (johnny profile), NOT the ARA sidecar. ARA is stopped.

## Setup facts

- **Mode:** `WHATSAPP_MODE=self-chat` — linked as a device on Greg's own account (`919582549236:94@s.whatsapp.net`); conversation happens in his Message Yourself thread. Session: `<profile>/whatsapp/session/` (`creds.json` present = paired).
- **The wizard needs a TTY** (`hermes whatsapp` calls `_require_tty`), so from an agent session automate pairing instead: run `node scripts/whatsapp-bridge/bridge.js --pair-json --pair-only --session <session_dir>`. It emits JSON lines on stdout: `{event:'qr',qr}` (a NEW qr string on each refresh), `{event:'connected',user}`, `{event:'error'}`. Bridge deps: `npm install --no-audit --no-fund` inside `scripts/whatsapp-bridge/` (node_modules is NOT committed in a git checkout).
- **QR delivery to Greg's screen:** render each qr string with `uv run --with "qrcode[pil]" python3 watcher.py` → save PNG → `open <png>` pops it on his Mac. He scans: WhatsApp → Settings → Linked Devices → Link a Device. On `connected`, `creds.json` exists → `hermes config set WHATSAPP_ENABLED true` → `hermes gateway restart`.

## Pitfalls (live-verified Oct 2026)

- **Allowlist is mandatory even in self-chat mode.** Without `WHATSAPP_ALLOWED_USERS=919582549236`, the gateway logs `Unauthorized user: 919582549236@s.whatsapp.net` and rejects every inbound message. The bridge's owner gate already suppresses the agent's own sent-message echo (no reply loop), but gateway authz still checks the allowlist. Set it with `hermes config set WHATSAPP_ALLOWED_USERS <number>` (routes into the profile's .env).
- **Never set `WHATSAPP_REPLY_PREFIX` via `hermes config set`** — it strips all non-ASCII characters (☤, ─) and double-escapes backslashes, so the value arrives mangled and the icon/separator vanish. Write the .env line directly instead: `WHATSAPP_REPLY_PREFIX=☤ *<name>*\n<separator>\n` (literal backslash-n; the bridge converts `\n` → real newline via `.replace(/\\n/g,'\n')`). Default when unset: `☤ *Hermes Agent*`. Verify the live bridge process env with `ps eww <bridge_pid>` — the key must carry the icon and a single literal `\n`.
- **Order matters:** set mode + allowlist BEFORE the restart; every env change requires a gateway restart (the adapter passes the env into the bridge process at spawn).

## Verify

- `hermes status` → Platforms must include WhatsApp.
- `grep whatsapp <profile>/logs/gateway.log` → `Bridge ready (status: connected)`, `✓ whatsapp connected` (bridge HTTP API on port 3000).
- Outbound smoke test: `hermes send -t "whatsapp:919582549236" "..."` → `sent`.
- Inbound E2E: Greg sends a message in his Message Yourself thread → gateway starts an agent turn and replies with the `☤ Hermes Agent` prefix.
