# Voice Note Transcription (Johnny WhatsApp gateway)

Greg sends voice notes over WhatsApp self-chat. They land un-transcribed in this profile —
assume auto-transcription is absent and transcribe manually before responding.

## File location

Voice audio lands at `~/.hermes/profiles/johnny/cache/documents/native-inputs/<hash>/aud_*.ogg`
(the exact path rides in the message the gateway delivers).

## Procedure

1. Convert to 16 kHz mono WAV:
`/root/.hermes/tools/ffmpeg-9.0.1-linux-x64/bin/ffmpeg -i <in.ogg> -f wav -ac 1 -ar 16000 /tmp/voicenote.wav -y`
2. Transcribe with ARA's Scribe module (ElevenLabs Scribe v2; the module loads its own API key
from /opt/ara/.env):
`cd /opt/ara && python3 -c "import scribe_stt; print(scribe_stt.transcribe_scribe('/tmp/voicenote.wav')['text'])"`
3. If that module is unavailable, call the ElevenLabs STT API directly (POST /v1/speech-to-text,
multipart file upload, model_id=scribe_v2) with ELEVENLABS_API_KEY from /opt/ara/.env, or fall
back to a local whisper install.

## Pitfalls

- Empty or whitespace-only transcript on the first call: retry once — the second call usually
returns the text.
- Proper nouns garble badly — car names above all ("an Ertiga" heard as "Antarctica").
Reconstruct meaning from context (amounts, vendors, previous messages) rather than taking the
literal transcription at face value; when it matters, state your interpretation to Greg for a
quick confirm instead of repeating garble.
