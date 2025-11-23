# Groq Integration Guide

## Overview

Shram.ai now supports **two LLM providers**: Anthropic Claude Sonnet 4.5 and Groq. You can easily switch between them using an environment variable.

## What Changed

### 1. Backend Configuration (`backend/app/core/settings.py`)

Added three new settings:

```python
use_groq: bool = os.getenv("USE_GROQ", "false").lower() == "true"
groq_api_key: str | None = os.getenv("GROQ_API_KEY")
groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
```

### 2. Dependencies (`backend/requirements.txt`)

Added Groq SDK:

```
groq==0.13.0
```

### 3. Orchestrator (`backend/app/agent/orchestrator.py`)

Major changes:

- **Multi-provider support**: TaskAgent now initializes either Anthropic or Groq client based on `USE_GROQ` setting
- **Tool format conversion**: Added `_convert_tools_for_groq()` to convert Anthropic tool format to OpenAI/Groq format
- **Message format conversion**: Added `_convert_messages_for_groq()` to handle different message formats
- **Streaming support**: Both Anthropic and Groq streaming are fully supported
- **Cost tracking**: Separate cost calculation for each provider (Groq is free during beta)
- **Logging**: Provider-aware logging to distinguish which LLM is being used

### 4. Documentation (`README.md`)

- Added comprehensive LLM Provider Options section
- Updated Prerequisites
- Updated Setup instructions with both options
- Updated architecture diagram
- Updated feature descriptions

## How to Use

### Option 1: Using Anthropic Claude (Default)

```bash
# .env file
USE_GROQ=false
ANTHROPIC_API_KEY=sk-ant-api03-xxxx
```

### Option 2: Using Groq

```bash
# .env file
USE_GROQ=true
GROQ_API_KEY=gsk_xxxx
GROQ_MODEL=llama-3.3-70b-versatile  # optional
```

## Available Groq Models

- `llama-3.3-70b-versatile` (default, best balance of speed and quality)
- `llama-3.1-70b-versatile` (good all-around performance)
- `llama-3.1-8b-instant` (fastest, best for simple tasks)
- `mixtral-8x7b-32768` (excellent for long context)
- `gemma2-9b-it` (efficient, good for resource-constrained environments)

## Comparison

| Feature | Anthropic Claude 4.5 | Groq |
|---------|---------------------|------|
| **Quality** | Best-in-class | Very good |
| **Speed** | ~30 tokens/sec | ~500 tokens/sec |
| **Tool Calling** | Advanced, very reliable | Good, reliable |
| **Cost** | $3/M input, $15/M output | Free (beta) |
| **Caching** | Yes (1 hour, 90% savings) | No |
| **Best For** | Production, complex tasks | Development, testing, speed |

## Technical Details

### Streaming Implementation

**Anthropic:**
- Uses `client.messages.stream()` with context manager
- Events: `content_block_start`, `content_block_delta`, `content_block_stop`
- Supports prompt caching with `cache_control` parameter
- Detailed token usage including cache metrics

**Groq:**
- Uses `client.chat.completions.create(stream=True)`
- Iterates over chunks with `delta` objects
- OpenAI-compatible format
- Token usage estimated (not provided by API during beta)

### Tool Format Conversion

Anthropic format:
```python
{
  "name": "create_task",
  "description": "...",
  "input_schema": {"type": "object", "properties": {...}}
}
```

Groq/OpenAI format:
```python
{
  "type": "function",
  "function": {
    "name": "create_task",
    "description": "...",
    "parameters": {"type": "object", "properties": {...}}
  }
}
```

### Cost Tracking

Both providers are tracked in the same `ApiCost` model. Groq costs are set to $0 during beta.

## Installation

1. Update dependencies:
```bash
cd backend
pip install -r requirements.txt
```

2. Configure your `.env` file with the provider of your choice

3. Restart the backend:
```bash
uvicorn app.main:app --reload
```

## Testing

The integration is production-ready. Both providers:
- ✅ Support all tool operations
- ✅ Handle streaming correctly
- ✅ Process voice commands
- ✅ Control the UI via `change_ui_view` tool
- ✅ Track conversation history
- ✅ Log costs and usage

## Switching Providers

You can switch providers at any time by:

1. Updating `USE_GROQ` in your `.env` file
2. Restarting the backend server

**No code changes or database migrations needed!**

## Future Enhancements

Potential improvements:
- Add support for more providers (OpenAI, Mistral, etc.)
- Real-time provider switching via API
- A/B testing between providers
- Provider fallback on errors
- Provider selection based on task complexity

## Questions?

- Anthropic docs: https://docs.anthropic.com/
- Groq docs: https://console.groq.com/docs
- Groq models: https://console.groq.com/docs/models

---

**Happy coding! 🚀**

