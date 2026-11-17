# Scribe v2 Indian Language Support — June 25, 2026

## Accuracy by Language (WER = Word Error Rate)

### Excellent (≤5% WER)
- Kannada
- Malayalam

### High Accuracy (5-10% WER)
- Hindi, Bengali, Gujarati, Marathi, Tamil, Telugu, Nepali, Odia

### Good (10-20% WER)
- Assamese, Punjabi

### Moderate (25-50% WER)
- Urdu, Sindhi

## Key Feature: Improved Indic-English Transcription

Scribe v2 handles code-switching correctly. When a speaker switches between an Indian language and English mid-sentence, English words remain in Latin script. No special language code needed — auto-detection works.

Example: "हमारे पास तीन options हैं — basic, premium, और enterprise" → transcribed with "options", "basic", "premium", "enterprise" in Latin script.

## Pricing

- **Batch (Scribe v2):** $0.22/hour ≈ ₹18/hour. A 15-minute meeting costs ₹4.50.
- **Realtime (Scribe v2 Realtime):** $0.39/hour ≈ ₹32/hour.

## Comparison to Previous STT

| Feature | Scribe v2 | faster-whisper small.en |
|---------|-----------|------------------------|
| Languages | 99 (including 11 Indian) | English only |
| Diarization | Built-in | None |
| Entity detection | 56 types | None |
| Long-form audio | Optimized | Degrades on silence |
| File format | Any audio/video | .ogg only |
| Cost | ₹18/hr | Free (CPU) |
