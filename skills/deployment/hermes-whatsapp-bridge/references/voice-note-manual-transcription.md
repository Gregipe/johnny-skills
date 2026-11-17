# Manual Voice-Note Transcription (auto-transcription failed)

When WhatsApp delivers a voice note as `voice message could not be transcribed
automatically; the audio is available at: <path>` there is NO other transcription
tool wired for this profile — run this verified pipeline (tested repeatedly, ~5s
per note):

1. Convert the .ogg to 16kHz mono WAV with the bundled ffmpeg (always at
   `/root/.hermes/tools/ffmpeg-9.0.1-linux-x64/bin/ffmpeg`):

   ```
   ffmpeg -i <audio-path>/aud_*.ogg -f wav -ac 1 -ar 16000 /tmp/voicenote.wav -y
   ```

2. Transcribe with ARA's Scribe v2 module (lives on this server, key already in
   `/opt/ara/.env`):

   ```
   cd /opt/ara && python3 -c "
   import scribe_stt
   r = scribe_stt.transcribe_scribe('/tmp/voicenote.wav')
   print(r['text'])
   "
   ```

   Returns `{'text': ..., 'segments': [...], 'language': ...}`. Use the
   top-level `text` field — `segments[].text` has broken double-spacing between
   words.

3. Read the transcript, then answer Greg as if he'd typed it. Prefix nothing;
   he treats voice notes as normal messages.

## Notes

- Cost is ~₹18/hour (Scribe v2) — a 10s note is fractions of a paisa. No reason
  to economize.
- The module needs the `.env` key formatted as `ELEVENLABS_API_KEY=sk_...`
  (raw key without the variable name reads as unavailable).
- Whisper fallback only matters if `/opt/ara` is gone or the key is dead; see
  the ara-voice skill for that path.
- Interim ack: transcription itself is fast enough that no separate
  "processing" message is needed, but if the note is long, ack first.
