# Dashboard Voice UI — Inline Chat-Anchored Mode

The working design as of July 3, 2026. A voice interaction mode anchored to the chat input bar — no full-screen overlay, no popup.

## Design

### Trigger

Mic button inside `.chat-input-wrap`, between textarea and send button. Icon: 5-bar waveform SVG (not a microphone emoji — looks modern, communicates "live conversation").

```html
<button class="mic-btn" id="chatMicBtn" title="Voice mode" onclick="toggleVoiceMode()">
  <svg width="22" height="22" viewBox="0 0 22 22">
    <rect x="2" y="9" width="3" height="4" rx="1.5" fill="currentColor"/>
    <rect x="7" y="5" width="3" height="12" rx="1.5" fill="currentColor"/>
    <rect x="12" y="2" width="3" height="18" rx="1.5" fill="currentColor"/>
    <rect x="17" y="7" width="3" height="8" rx="1.5" fill="currentColor"/>
  </svg>
</button>
```

### Active State

- Chat input fades to 40% opacity, becomes non-interactive
- Floating voice control appears centered above the composer (72px circle, accent color background)
- Waveform ring around the button (radial bars, ~32 bars)
- Status chip below: "Connecting...", "Listening", "Thinking...", tool name during tool calls

### Button States

| State | CSS class | Animation | Visual |
|-------|-----------|-----------|--------|
| Idle | — | None | Gray waveform bars |
| Connecting | — | None | Status: "Connecting..." |
| Listening | `.listening` | `voice-breathe` 1.2s scale 1.0→1.08 | Waveform reacts to mic volume |
| Thinking | `.thinking` | `voice-think` 1.6s opacity pulse + rotating gradient ring | Waveform hidden, ring visible |
| Speaking | `.speaking` | `voice-speak` 0.6s scale pulse | Waveform reacts to playback amplitude |

### Ending

- Tap the floating button or press Esc
- Button shrinks back into chat input
- Input regains opacity and focus
- 250ms transition

## Audio Output

The most commonly broken piece. Three rules:

1. **Create the audio element inside the click handler** (satisfies browser autoplay policy)
2. **Pass `playoutElement` to `SmallWebRTCTransport`**
3. **Call `.play()` after connection** and again after 500ms (catches lazy-attached streams)

```javascript
const audioEl = document.createElement('audio');
audioEl.autoplay = true;
audioEl.playsInline = true;
document.body.appendChild(audioEl);
window._voiceAudioEl = audioEl;

const transport = new SmallWebRTCTransport({ playoutElement: audioEl });

// After connect:
await pcClient.connect(...);
audioEl.play().catch(function(){});
setTimeout(function() {
  document.querySelectorAll('audio').forEach(function(a) {
    a.play().catch(function(){});
  });
}, 500);
```

### Common Failure: Silence Despite Working Pipeline

Symptom: Server logs show full pipeline (STT→LLM→TTS all firing, `bot-output` and `bot-tts-text` messages stream), browser console shows "Remote track unmuted: microphone", but Greg hears nothing.

Root cause: The WebRTC remote audio track arrives but no DOM audio element has `srcObject` set to the stream. The `SmallWebRTCTransport` handles `playoutElement` attachment internally, but only if it's passed at construction time.

## WebRTC Client

Uses `@pipecat-ai/small-webrtc-transport` and `@pipecat-ai/client-js` from esm.sh:

```javascript
import { SmallWebRTCTransport } from 'https://esm.sh/@pipecat-ai/small-webrtc-transport@1.10';
import { PipecatClient } from 'https://esm.sh/@pipecat-ai/client-js@1.11';
```

**Endpoint**: Must be same-origin to avoid CORS. Use `/voice/start` (proxied through ARA's FastAPI to Pipecat on localhost:8768). Never use ngrok URL directly from dashboard JS.

## Events to State Mapping

| Client event | UI state change |
|-------------|-----------------|
| `bot-connected` | → listening |
| `bot-disconnected` | → end voice mode |
| `user-started-speaking` | → listening (waveform active) |
| `user-stopped-speaking` | → thinking |
| `bot-llm-started` | → thinking |
| `bot-llm-text` | → stream transcript to chat |
| `bot-llm-tool-call-starting` | → status chip: tool name |
| `bot-tts-started` | → speaking |
| `bot-stopped-speaking` | → listening |
| `bot-error` | → end voice mode |

## Template Patching Pitfalls

- **`dashboard_template.py` is a Python module, not static HTML** — it's a `DASHBOARD_HTML = """..."""` string with Jinja-style `{{COMPANY}}` placeholders. After patching: delete `__pycache__`, restart ARA.
- **Shell escaping in patch scripts** — prefer standalone Python patch scripts over inline heredocs/one-liners. Emojis, backslashes, and triple-quotes frequently break shell escaping.
- **The mic button placement** — must go inside `.chat-input-wrap`, between textarea and send button. Use the exact line match for `'<button class="send-btn"'` as the anchor.
