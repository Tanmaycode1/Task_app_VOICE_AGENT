# Groq API Analysis

## Overview

Groq provides fast AI inference services with OpenAI-compatible API format. Their API is designed for low-latency LLM inference.

## API Endpoint

**Base URL**: `https://api.groq.com/openai/v1`

**Chat Completions**: `POST https://api.groq.com/openai/v1/chat/completions`

## Request Format

Groq uses **OpenAI-compatible** API format, making it easy to switch from OpenAI/Anthropic:

```python
import groq

client = groq.Groq(api_key="your-api-key")

response = client.chat.completions.create(
    model="llama-3.1-8b-instant",  # or other models
    messages=[
        {"role": "user", "content": "Your query here"}
    ],
    temperature=0.7,
    max_tokens=1024,
    tools=[...],  # Tool calling support
    tool_choice="auto"
)
```

### Example Request (JSON)

```json
{
  "model": "llama-3.1-8b-instant",
  "messages": [
    {
      "role": "user",
      "content": "Explain the importance of low latency LLMs"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 1024
}
```

## Response Format

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1677858242,
  "model": "llama-3.1-8b-instant",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Response text here..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 50,
    "total_tokens": 60
  }
}
```

## Available Models

### Recommended for Task Management:

1. **Llama 3.1 8B Instant 128k**
   - Fast, efficient
   - Good for simple queries
   - Input: $0.05/M tokens
   - Output: $0.08/M tokens

2. **Llama 3.3 70B Versatile 128k**
   - More capable
   - Better for complex queries
   - Input: $0.59/M tokens
   - Output: $0.79/M tokens

3. **Mixtral 8x7B** (if available)
   - Good balance
   - Check current pricing

## Pricing (Per Million Tokens)

| Model | Input Tokens | Output Tokens |
|-------|--------------|---------------|
| **Llama 3.1 8B Instant** | $0.05 | $0.08 |
| **Llama 3.3 70B Versatile** | $0.59 | $0.79 |
| **GPT-OSS 20B** | $0.075 | $0.30 |
| **GPT-OSS 120B** | $0.15 | $0.60 |

### Cost Comparison vs Claude Sonnet 4.5

**Claude Sonnet 4.5:**
- Input: $3.00/M tokens
- Output: $15.00/M tokens

**Groq Llama 3.1 8B:**
- Input: $0.05/M tokens (60x cheaper!)
- Output: $0.08/M tokens (187x cheaper!)

**Example Cost Savings:**
- Simple query: 5,500 input + 100 output tokens
- Claude: (5,500 × $3/1M) + (100 × $15/1M) = $0.0165 + $0.0015 = **$0.018**
- Groq: (5,500 × $0.05/1M) + (100 × $0.08/1M) = $0.000275 + $0.000008 = **$0.000283**
- **Savings: ~98.4% cheaper!**

## Tool Calling Support

Groq supports OpenAI-compatible tool calling:

```python
response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[...],
    tools=[
        {
            "type": "function",
            "function": {
                "name": "create_task",
                "description": "Create a new task",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "scheduled_date": {"type": "string"}
                    },
                    "required": ["title", "scheduled_date"]
                }
            }
        }
    ],
    tool_choice="auto"
)
```

**Note**: Tool calling reliability may vary by model. Llama 3.3 70B likely has better tool calling than 8B.

## Python SDK Installation

```bash
pip install groq
```

## Streaming Support

Groq supports streaming responses:

```python
stream = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[...],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

## Key Advantages

1. **Ultra-Fast**: Low latency inference
2. **Cost-Effective**: Much cheaper than Claude
3. **OpenAI-Compatible**: Easy migration
4. **Tool Calling**: Supports function calling
5. **Streaming**: Real-time response generation

## Limitations

1. **Tool Calling Reliability**: May be lower than Claude (70-85% vs 95%+)
2. **Complex Reasoning**: May struggle with complex multi-step operations
3. **Large System Prompts**: Smaller models may not follow 4000+ token prompts as well
4. **Model Selection**: Need to choose right model for task complexity

## Recommended Usage Strategy

### For Simple Queries (Level 1):
- **Model**: Llama 3.1 8B Instant
- **Use Cases**: Basic list/show, simple navigation, explicit dates
- **Expected Accuracy**: 85-90% tool calling
- **Cost**: ~$0.0003 per query

### For Medium Queries (Level 2):
- **Model**: Llama 3.3 70B Versatile
- **Use Cases**: Date inference, ambiguous references, multi-tool ops
- **Expected Accuracy**: 90-95% tool calling
- **Cost**: ~$0.003 per query (still 7x cheaper than Claude)

### For Complex Queries (Level 3):
- **Model**: Claude Sonnet 4.5 (keep using)
- **Use Cases**: History operations, planning, multi-step reasoning
- **Expected Accuracy**: 95%+ tool calling
- **Cost**: ~$0.022 per query

## Integration Example

```python
from groq import Groq

class GroqTaskAgent:
    def __init__(self, db: Session):
        self.db = db
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.1-8b-instant"
    
    async def process_query(self, query: str):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": query}
            ],
            tools=TOOLS,
            temperature=0.7,
            max_tokens=2048
        )
        
        # Extract usage
        usage = response.usage
        input_tokens = usage.prompt_tokens
        output_tokens = usage.completion_tokens
        
        # Process response...
        return response
```

## API Key Setup

1. Sign up at https://console.groq.com
2. Get API key from dashboard
3. Add to `.env`: `GROQ_API_KEY=your_key_here`

## Rate Limits

Check Groq documentation for current rate limits. They typically offer generous free tier.

## References

- **Documentation**: https://console.groq.com/docs
- **Pricing**: https://groq.com/pricing
- **Python SDK**: `pip install groq`

---

**Last Updated**: Based on web search results
**Recommendation**: Test Llama 3.1 8B for simple queries first, then evaluate tool calling accuracy before full migration.

