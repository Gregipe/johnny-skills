# Dashboard Voice Chat Display

How to render voice transcriptions in the ARA dashboard chat panel — formatting, event wiring, and user preferences.

## CSS — match normal Ava chat font

Voice transcript lines must match the normal Ava chat styling, not use italic or grey text:

```css
.voice-transcript-line {
  font-size: 13px;
  line-height: 1.5;
  color: #111111;
  padding: 4px 0;
}
```

The normal chat agent messages use: `font-size: 13px; line-height: 1.5; color: #111111` in `.chat-msg.agent`. Voice transcripts should be indistinguishable from normal chat in font and color. No italic. No grey.

## User transcript — show STT output

Listen for `userTranscript` events (camelCase — see pitfall #22 in pipecat-voice-agent). Append as a separate line in grey so the user can see what was transcribed:

```javascript
pcClient.on('userTranscript', (data) => {
  if (data.text && data.final) {
    const line = document.createElement('div');
    line.className = 'voice-transcript-line';
    line.style.color = '#6B7280';
    line.textContent = 'You: ' + data.text;
    chatMsg.appendChild(line);
    chatMsg.scrollTop = chatMsg.scrollHeight;
  }
});
```

Key: check `data.final` — only append finalized transcripts, not mid-speech partials. The `userTranscript` event fires continuously as speech is recognized.

## Bot transcript — accumulate per-line

`botLlmText` fires per token/word. Accumulate in a single div for the current utterance, then clear on `botStoppedSpeaking`:

```javascript
let currentBotLine = null;

pcClient.on('botLlmText', (e) => {
  if (e.text) {
    if (!currentBotLine) {
      currentBotLine = document.createElement('div');
      currentBotLine.className = 'voice-transcript-line';
      currentBotLine.textContent = 'Ava: ';
      chatMsg.appendChild(currentBotLine);
    }
    currentBotLine.textContent += e.text;
    chatMsg.scrollTop = chatMsg.scrollHeight;
  }
});

pcClient.on('botStoppedSpeaking', () => {
  currentBotLine = null;
  setVoiceState('listening');
});
```

## Result

Voice chat looks like a conversation:

```
Ava: What can I help with today?
You: What's my pipeline summary?
Ava: You have four active deals. Acme Logistics is in negotiation — that's your closest to close. Xpressbees is at reached out. Two more in new.
```

User lines in grey, Ava lines in black, same font as normal chat. User can immediately spot transcription errors and correct them.

## TTS Pronunciation: timezone abbreviations

ElevenLabs TTS pronounces "IST" as "eyeest" (rhymes with "feast"). Fix: add a pronunciation instruction to the voice system prompt:

```
Pronunciation: Say timezone abbreviations as letters, e.g. "I S T" not "ist" or "eyeest".
Read acronyms as individual letters when they represent a timezone or standard.
```

The LLM then writes "I S T" in its response, which TTS reads as individual letters. This is a prompt-level fix — the TTS model isn't being told to change pronunciation; the LLM is told to write the correct text in the first place.
