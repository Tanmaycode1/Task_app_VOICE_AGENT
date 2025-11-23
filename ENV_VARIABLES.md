# Environment Variables Reference

## Required Variables

### Deepgram (Voice Transcription)
```bash
DEEPGRAM_API_KEY=your_deepgram_api_key_here
```
Get your key: https://deepgram.com

---

## LLM Provider (Choose One)

### Option 1: Anthropic Claude (Default, Recommended)

```bash
USE_GROQ=false
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxx
```

**Get your key:** https://console.anthropic.com/

**Features:**
- Best quality and reasoning
- Advanced tool calling
- Prompt caching (saves ~90%)
- $3/M input, $15/M output

---

### Option 2: Groq (Free, Ultra-Fast)

```bash
USE_GROQ=true
GROQ_API_KEY=gsk_xxxxxxxxxxxx
GROQ_MODEL=llama-3.3-70b-versatile
```

**Get your key:** https://console.groq.com/

**Available Models:**
- `llama-3.3-70b-versatile` (default, best balance)
- `llama-3.1-70b-versatile` (good performance)
- `llama-3.1-8b-instant` (fastest)
- `mixtral-8x7b-32768` (long context)
- `gemma2-9b-it` (efficient)

**Features:**
- ~500 tokens/sec (super fast!)
- Free during beta
- Good tool calling
- Great for development

---

## Optional Variables

### Database
```bash
DATABASE_PATH=shram.db
```
Path to SQLite database file. Defaults to `shram.db` in backend directory.

### Project Configuration
```bash
PROJECT_NAME="Shram AI Backend"
PROJECT_VERSION="0.1.0"
API_PREFIX="/api"
ENVIRONMENT="local"
```

---

## Complete .env Examples

### Example 1: Production (Anthropic)
```bash
# Voice transcription
DEEPGRAM_API_KEY=your_deepgram_key_here

# LLM (Anthropic Claude)
USE_GROQ=false
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxx

# Database
DATABASE_PATH=shram.db

# Optional
PROJECT_NAME="Shram AI Backend"
ENVIRONMENT="production"
```

### Example 2: Development (Groq)
```bash
# Voice transcription
DEEPGRAM_API_KEY=your_deepgram_key_here

# LLM (Groq - Free & Fast)
USE_GROQ=true
GROQ_API_KEY=gsk_xxxxxxxxxxxx
GROQ_MODEL=llama-3.3-70b-versatile

# Database
DATABASE_PATH=shram.db

# Optional
PROJECT_NAME="Shram AI Backend"
ENVIRONMENT="local"
```

### Example 3: Testing (Groq Fast Model)
```bash
# Voice transcription
DEEPGRAM_API_KEY=your_deepgram_key_here

# LLM (Groq - Fastest model)
USE_GROQ=true
GROQ_API_KEY=gsk_xxxxxxxxxxxx
GROQ_MODEL=llama-3.1-8b-instant

# Database
DATABASE_PATH=shram.db
```

---

## Quick Setup

1. Copy one of the examples above
2. Create `.env` file in `backend/` directory:
   ```bash
   cd backend
   nano .env  # or use your preferred editor
   ```
3. Paste and modify with your actual API keys
4. Save and restart backend:
   ```bash
   uvicorn app.main:app --reload
   ```

---

## Troubleshooting

### "ANTHROPIC_API_KEY environment variable is required"
- You have `USE_GROQ=false` (or not set) but no `ANTHROPIC_API_KEY`
- Solution: Add `ANTHROPIC_API_KEY` or switch to Groq with `USE_GROQ=true`

### "GROQ_API_KEY environment variable is required"
- You have `USE_GROQ=true` but no `GROQ_API_KEY`
- Solution: Add `GROQ_API_KEY` or switch to Anthropic with `USE_GROQ=false`

### Want to switch providers?
Just change `USE_GROQ` and restart:
```bash
# Switch to Groq
USE_GROQ=true

# Switch to Anthropic
USE_GROQ=false
```

---

## Security Notes

⚠️ **NEVER commit your `.env` file to version control!**

The `.env` file contains sensitive API keys. It should be:
- Listed in `.gitignore`
- Kept secret and secure
- Not shared publicly
- Regenerated if compromised

For production deployments, use environment variables through your hosting platform (Render, Vercel, Railway, etc.) instead of a `.env` file.

---

**Happy coding! 🔐**

