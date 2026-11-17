# Dashboard Voice Overlay — Claude-style Full-Screen Orb

Date: 2026-07-03 (Phase 1 implementation)

The ARA dashboard voice mode uses a full-screen dark overlay with a single
animated orb, status label, rolling caption, and bottom controls — modeled
on the Claude desktop voice mode.

## HTML Structure

```html
<div class="voice-overlay-backdrop" id="voiceOverlay">
  <div class="voice-orb" id="voiceOrb"></div>
  <div class="voice-status-label" id="voiceStatus">Connecting…</div>
  <div class="voice-caption" id="voiceCaption"></div>
  <audio id="ttsAudio" style="display:none"></audio>
  <div class="voice-controls">
    <button class="voice-ctrl-btn" id="voiceMuteBtn">🎤</button>
    <button class="voice-ctrl-btn end" id="voiceEndBtn">✕</button>
  </div>
</div>

<!-- Floating mic FAB in the dashboard -->
<button class="voice-fab" id="voiceFab">🎙️</button>
```

## Orb States

Four states driven by Pipecat client events:

| State | CSS class | Trigger event | Animation |
|-------|-----------|---------------|-----------|
| Connecting | `connecting` | On overlay open | Slow opacity pulse (2s) |
| Listening | `listening` | `bot-connected` | Gentle breathing scale (2s) |
| Thinking | `thinking` | `bot-llm-tool-call-starting` | Fast pulse (0.8s), purple hue |
| Speaking | `speaking` | `bot-started-speaking` | Rhythmic beat (0.4s), brighter glow |
| Muted | `muted` | Mute toggle | Amber border on orb |

## Client Event Mapping

```javascript
pcClient.on('bot-connected', () => { setOrbState('listening'); });
pcClient.on('bot-disconnected', () => { cleanup(); });
pcClient.on('bot-llm-tool-call-starting', (e) => { setOrbState('thinking'); showToolChip(e); });
pcClient.on('bot-started-speaking', () => { setOrbState('speaking'); });
pcClient.on('bot-stopped-speaking', () => { setOrbState('listening'); });
pcClient.on('bot-llm-text', (e) => { showCaption(e.text); });
```

## Status Chips During Tool Calls

Map tool names to human-readable labels, not raw `search_leads`:

```javascript
const TOOL_LABELS = {
  search_leads: 'Looking up your leads',
  get_pipeline_summary: 'Checking your pipeline',
  get_summary: 'Getting activity summary',
  get_action_items: 'Checking action items',
  // ...
};
```

## Token-Based Auth Flow

1. Dashboard JS calls `POST /api/voice/session` (same-origin, no auth header needed — ARA derives tenant from session)
2. ARA returns `{voice_token}` — single-use, 60s TTL, stored in `_voice_tokens` dict
3. Dashboard JS passes `{voice_token}` in the `/start` body to Pipecat
4. Pipecat's `bot()` reads `runner_args.body.voice_token`, calls `POST /api/voice/session/verify` with `X-Voice-Secret` header
5. ARA **consumes** the token (dict.pop), returns `{tenant_id}`
6. `tenant_id` goes into `app_resources`, used in every subsequent `/api/voice/tool` call

## WebRTC Client

Uses `@pipecat-ai/small-webrtc-transport` and `@pipecat-ai/client-js` from esm.sh:

```javascript
import { SmallWebRTCTransport } from '...small-webrtc-transport@1.10';
import { PipecatClient } from '...client-js@1.11';

const transport = new SmallWebRTCTransport({ pcmAudio: true, playoutElement: audioEl });
const client = new PipecatClient({ transport });
await client.connect({
  endpoint: VOICE_ENDPOINT,
  body: JSON.stringify({ voice_token: token }),
});
```

## Security Rules

- `X-Voice-Secret` NEVER appears in JavaScript, templates, or rendered HTML
- `tenant_id` NEVER originates from the client — always server-derived via token
- Tokens are single-use (consumed on read), 60-second TTL
- Gate test: `grep X-Voice-Secret /opt/ara/dashboard_template.py` MUST return empty

## CSS Animations (Keyframes)

```css
@keyframes orb-pulse-slow { 0%,100%{opacity:0.5} 50%{opacity:0.8} }
@keyframes orb-breathe { 0%,100%{transform:scale(1.0)} 50%{transform:scale(1.06)} }
@keyframes orb-pulse-fast { 0%,100%{transform:scale(1.0);opacity:0.7} 50%{transform:scale(1.04);opacity:1} }
@keyframes orb-beat { 0%,100%{transform:scale(1.0)} 30%{transform:scale(1.08)} 60%{transform:scale(0.96)} }
```

## File Location

Dashboard code is in `/opt/ara/dashboard_template.py` — a single-file HTML
template rendered by `server.py`'s `/dashboard` route. The overlay HTML and
`<script type="module">` block are inserted before the closing `</body>` tag.
