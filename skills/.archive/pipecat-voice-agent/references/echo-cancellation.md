# Echo Cancellation for Pipecat Voice Agent Dashboard

Browser-level acoustic echo cancellation (AEC) prevents the bot from hearing its own TTS output through the user's speakers.

## Problem

When the user uses speakers (not headphones), the microphone picks up the bot's TTS audio. The STT transcribes it, Pipecat's `TranscriptionUserTurnStartStrategy` detects "user speech," and `allow_interruptions=True` fires `bot-interrupted` — cutting off the bot mid-sentence.

VAD tuning (`start_secs`, `min_volume`, `confidence`) does NOT fix this because Pipecat 1.4.0+ defaults to `TranscriptionUserTurnStartStrategy` for barge-in, not VAD-based start detection.

## Fix: getUserMedia Monkey-Patch

Inject AEC constraints into every `getUserMedia` call BEFORE Pipecat imports. Pipecat's `SmallWebRTCTransport` calls `getUserMedia` internally, so the monkey-patch must run in a synchronous IIFE before any `import` statements.

```javascript
(function() {
  var OrigGUM = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  navigator.mediaDevices.getUserMedia = function(constraints) {
    if (!constraints) constraints = { audio: true };
    if (constraints.audio === true) constraints.audio = {};
    if (constraints.audio && typeof constraints.audio === 'object') {
      constraints.audio.echoCancellation = true;
      constraints.audio.noiseSuppression = true;
      constraints.audio.autoGainControl = true;
    }
    return OrigGUM(constraints);
  };
})();
```

Place this in a `<script type="module">` block BEFORE the Pipecat imports:
```javascript
import { SmallWebRTCTransport } from '...';
```

## Caveats

- Only works if the browser supports WebRTC AEC (Chrome, Edge, Safari do; Firefox has limited support)
- Does NOT help if the echo path is through the OS audio stack (e.g., system-level loopback)
- If the user is on a call with the bot AND has speakers loud enough to create a feedback loop, AEC may not fully eliminate it
- The definitive test: use headphones. If interruptions stop → it's echo. If they continue → investigate VAD or Smart Turn.
