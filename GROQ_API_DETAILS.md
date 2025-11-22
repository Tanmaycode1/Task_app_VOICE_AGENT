# Groq API - Complete Reference

## 🎯 **Overview**

Groq provides ultra-fast LLM inference with **OpenAI-compatible API** format, making migration straightforward.

---

## 📡 **API Compatibility**

### **OpenAI Compatible**
```python
# Works with OpenAI SDK with minimal changes!
from openai import OpenAI

client = OpenAI(
    api_key="YOUR_GROQ_API_KEY",
    base_url="https://api.groq.com/openai/v1"
)

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

---

## 💰 **Pricing (January 2025)**

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Speed | Tool Calling |
|-------|----------------------|------------------------|-------|--------------|
| **llama-3.3-70b-versatile** | $0.59 | $0.79 | Ultra-fast | ✅ Yes |
| **llama-3.1-8b-instant** | $0.05 | $0.08 | Blazing! | ✅ Yes |
| **llama-3.1-70b-versatile** | $0.59 | $0.79 | Fast | ✅ Yes |
| **mixtral-8x7b** | $0.24 | $0.24 | Fast | ✅ Yes |
| **gemma2-9b-it** | $0.20 | $0.20 | Fast | ✅ Yes |

### **With Prompt Caching (Automatic)**
- **Cached Input**: 50% discount (e.g., $0.59 → $0.295)
- **Output**: No discount ($0.79 remains $0.79)

---

## ⚡ **Prompt Caching**

### **How It Works**
- **Automatic**: No code changes required!
- **Prefix Matching**: Caches identical prompt prefixes
- **Duration**: Few hours (auto-expires)
- **Discount**: 50% on cached input tokens
- **Not Guaranteed**: Depends on internal routing

### **Example**
```
Request 1: "System prompt + tools + user query"
→ Creates cache, full price

Request 2: "System prompt + tools + different query"  
→ Cache hit on "System prompt + tools"
→ Only "different query" charged full price
→ 50% savings on cached portion
```

### **Best Practices**
1. Put **static content first** (system prompt, tools, examples)
2. Put **dynamic content last** (user query, context)
3. Keep prompts structured consistently

---

## 🛠️ **Tool Calling (Function Calling)**

### **Status: ✅ SUPPORTED**

Models with tool calling:
- llama-3.3-70b-versatile
- llama-3.1-70b-versatile
- llama-3.1-8b-instant
- mixtral-8x7b

### **Format: OpenAI Compatible**
```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name"
                    }
                },
                "required": ["location"]
            }
        }
    }
]

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "What's the weather in SF?"}],
    tools=tools,
    tool_choice="auto"
)
```

### **Response Format**
```python
# Tool call response
{
    "choices": [{
        "message": {
            "role": "assistant",
            "tool_calls": [{
                "id": "call_123",
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "arguments": '{"location": "San Francisco"}'
                }
            }]
        }
    }]
}
```

---

## 🌊 **Streaming**

### **✅ Fully Supported**
```python
stream = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### **Streaming with Tools**
```python
# Same as OpenAI - streams tool calls incrementally
for chunk in stream:
    delta = chunk.choices[0].delta
    if delta.tool_calls:
        print(f"Tool: {delta.tool_calls[0].function.name}")
```

---

## 🔑 **Authentication**

```bash
# Get API key from: https://console.groq.com/keys
export GROQ_API_KEY="gsk_..."
```

```python
# In code
client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)
```

---

## 📊 **Response Format**

### **Standard Response**
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "llama-3.3-70b-versatile",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Hello! How can I help?"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 8,
    "total_tokens": 18,
    "prompt_tokens_details": {
      "cached_tokens": 0  // Groq-specific: cache hit info
    }
  }
}
```

---

## ⚖️ **Groq vs Anthropic (Claude)**

| Feature | Anthropic Claude | Groq |
|---------|-----------------|------|
| **Price (70B)** | $3/$15 per 1M tokens | $0.59/$0.79 per 1M tokens |
| **Speed** | Fast | **Ultra-fast** (10x faster) |
| **Cache Discount** | **90%** ($3 → $0.30) | 50% ($0.59 → $0.295) |
| **Cache Control** | ✅ Explicit (`cache_control`) | ⚠️ Automatic (no control) |
| **Cache Guarantee** | ✅ Yes (same API key) | ⚠️ No (routing-dependent) |
| **Cache Duration** | 5 min → 1 hour (extended) | Few hours (unknown) |
| **Cache Shared** | ✅ Org-wide | ⚠️ Per-instance |
| **Tool Calling** | ✅ Excellent (>95% reliability) | ✅ Good |
| **Reasoning** | ✅ Excellent (complex tasks) | ⚠️ Good (simpler tasks) |
| **Context Window** | 200K tokens | 128K tokens |

---

## 🎯 **When to Use Groq**

### **✅ GREAT FOR:**
- Simple queries (navigation, listing)
- High-volume, low-complexity workloads
- Budget-conscious applications
- Speed-critical applications
- Tasks without complex reasoning

### **❌ NOT IDEAL FOR:**
- Complex multi-step reasoning
- Critical tool calling reliability
- Tasks requiring guaranteed caching
- Long context tasks (>128K tokens)

---

## 💡 **Hybrid Strategy**

### **Route by Complexity**

```python
def route_to_model(query: str, has_tools: bool) -> str:
    """Intelligent LLM routing"""
    
    # Complex = use Claude
    if has_tools or len(query) > 200 or any(kw in query.lower() for kw in 
        ["plan", "schedule", "multiple", "restore", "revert"]):
        return "claude-sonnet-4"  # $3/$15, 90% cache
    
    # Simple = use Groq
    else:
        return "llama-3.3-70b"  # $0.59/$0.79, 50% cache
```

### **Cost Comparison**

**100 queries (50 simple, 50 complex):**

**All Claude:**
- Cost: 100 × $0.015 = $1.50
- Quality: Excellent

**Hybrid (Groq for simple, Claude for complex):**
- Simple: 50 × $0.002 = $0.10 (Groq)
- Complex: 50 × $0.015 = $0.75 (Claude)
- **Total: $0.85** (43% cheaper!)
- Quality: Excellent where it matters

---

## 🔧 **Migration from Claude to Groq**

### **Minimal Changes Needed**

```python
# BEFORE (Anthropic)
import anthropic
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
response = client.messages.create(
    model="claude-sonnet-4",
    max_tokens=1024,
    system="You are helpful",
    messages=[{"role": "user", "content": "Hello"}]
)

# AFTER (Groq with OpenAI SDK)
from openai import OpenAI
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)
response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    max_tokens=1024,
    messages=[
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Hello"}
    ]
)
```

### **Key Differences:**
1. **System message**: Separate in Anthropic, in messages array for Groq/OpenAI
2. **SDK**: `anthropic` → `openai`
3. **Method**: `messages.create` → `chat.completions.create`
4. **Response**: `.content[0].text` → `.choices[0].message.content`

---

## 📚 **Resources**

- **Docs**: https://console.groq.com/docs
- **Pricing**: https://groq.com/pricing
- **Caching**: https://console.groq.com/docs/prompt-caching
- **API Keys**: https://console.groq.com/keys
- **Examples**: https://github.com/groq/groq-api-cookbook

---

## ✅ **Summary**

**Groq is GREAT for:**
- 🚀 **Speed** (10x faster than Claude)
- 💰 **Cost** (5x cheaper than Claude)
- 🔧 **Easy migration** (OpenAI-compatible)

**Claude is BETTER for:**
- 🧠 **Complex reasoning**
- 🎯 **Guaranteed caching** (90% savings)
- 🛠️ **Tool calling reliability** (>95%)
- 📝 **Long context** (200K tokens)

**RECOMMENDATION: Use both!**
- Groq for simple queries → Save 90% on those
- Claude for complex tasks → Get best quality where it matters
- Combined: Save 40-50% overall with zero quality loss

