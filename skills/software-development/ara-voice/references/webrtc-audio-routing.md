# WebRTC Audio Routing — Global RTCPeerConnection Monkey-Patch

## Problem

The Pipecat `SmallWebRTCTransport` wraps WebRTC signaling but does NOT attach remote audio tracks to a DOM element. The browser receives the remote audio track ("Remote track unmuted: microphone"), but Greg hears silence. The `playoutElement` config option exists but fails reliably because:
1. The audio element must be created inside a user gesture to satisfy autoplay policy
2. `SmallWebRTCTransport` creates the RTCPeerConnection internally — we can't intercept tracks directly
3. Module imports cache the original `RTCPeerConnection` — monkey-patching too late has no effect

## Solution

Monkey-patch `RTCPeerConnection` in an IIFE that runs BEFORE any Pipecat module imports. The patch intercepts EVERY `setRemoteDescription` call and adds a `track` listener whenever the SDP contains `m=audio`.

## Code

```javascript
<script>
// MUST run before any module imports
(function() {
  var OrigRTCPC = window.RTCPeerConnection || window.webkitRTCPeerConnection;
  if (OrigRTCPC) {
    window.RTCPeerConnection = function() {
      var pc = new OrigRTCPC(arguments[0]);
      var origSetRemote = pc.setRemoteDescription.bind(pc);
      pc.setRemoteDescription = function(desc) {
        if (desc && desc.sdp && desc.sdp.indexOf('m=audio') > -1) {
          pc.addEventListener('track', function(evt) {
            if (evt.track.kind === 'audio') {
              var stream = evt.streams[0] || new MediaStream([evt.track]);
              var audioEl = document.createElement('audio');
              audioEl.className = 'voice-output';
              audioEl.autoplay = true;
              audioEl.playsInline = true;
              audioEl.setAttribute('playsinline', '');
              audioEl.style.display = 'none';
              document.body.appendChild(audioEl);
              audioEl.srcObject = stream;
              audioEl.play().catch(function(e) { console.log('Audio play blocked:', e.message); });
            }
          }, {once: true});
        }
        return origSetRemote(desc);
      };
      return pc;
    };
  }
})();
</script>

<script type="module">
// Pipecat imports come AFTER the monkey-patch
import { SmallWebRTCTransport } from 'https://esm.sh/@pipecat-ai/small-webrtc-transport@1.10';
import { PipecatClient } from 'https://esm.sh/@pipecat-ai/client-js@1.11';
// ... rest of voice mode code
</script>
```

## Key Details

- The IIFE must be in a regular `<script>` tag, NOT `type="module"` — modules execute in order but the monkey-patch needs to run before module imports are evaluated
- `window.RTCPeerConnection` is the browser global that ALL libraries (including `SmallWebRTCTransport`) read from
- `{once: true}` prevents duplicate tracks from creating extra audio elements
- The `audioEl` is hidden but must be appended to `document.body` — browsers won't play detached audio elements
- The `setRemoteDescription` interception is the right hook point because it's called AFTER the ICE handshake completes and remote tracks are available

## Why playoutElement Fails

`SmallWebRTCTransport({ playoutElement: audioEl })` requires the audio element to be:
1. Created inside a user gesture (autoplay policy)
2. Appended to the document
3. Have `autoplay: true`

Even with all three, the transport may not call `.play()` or may create the element before `srcObject` is set. The monkey-patch approach is more reliable because it fires on the actual `track` event, which guarantees `srcObject` is ready.

## Cleanup

On voice mode end, remove any audio elements created by the patch:
```javascript
document.querySelectorAll('audio.voice-output').forEach(function(el) { el.remove(); });
```

## Verified On

- macOS Safari 26.x
- Pipecat 1.4.0 server-side, client-js 1.10/1.11
- July 3, 2026 — ARA dashboard voice integration
