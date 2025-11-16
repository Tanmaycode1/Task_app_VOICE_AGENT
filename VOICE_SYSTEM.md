# Voice System

## How It Works

1. **Speech-to-Text**: Deepgram FLUX for real-time voice transcription
2. **Text-to-Speech**: Browser's native Web Speech API (no external API needed)

## Flow

```
User speaks → Microphone captures audio
  → Deepgram FLUX transcribes to text
  → Agent processes and responds
  → Browser TTS speaks response
  → Microphone disabled during speech
  → Speech ends → Microphone re-enabled
```

## Features

- ✅ No API delays for TTS (instant browser playback)
- ✅ Microphone auto-disabled during agent speech (prevents echo)
- ✅ User can interrupt by speaking
- ✅ Duplicate speech prevention
- ✅ Works offline (TTS only, STT needs Deepgram)

## Environment Variables

Only need Deepgram API key for speech-to-text (already configured in backend):

```bash
# Backend only
DEEPGRAM_API_KEY=your_key_here
```

Frontend doesn't need any special configuration for TTS - it uses the browser's built-in speech synthesis.
