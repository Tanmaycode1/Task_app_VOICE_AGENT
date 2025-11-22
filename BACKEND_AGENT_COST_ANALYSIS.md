# Backend Agent Orchestration - Model & Cost Analysis

## Model Configuration

### Primary Model
- **Model**: Claude Sonnet 4.5
- **Model ID**: `claude-sonnet-4-20250514`
- **Provider**: Anthropic
- **Location**: `backend/app/agent/orchestrator.py`

### Model Parameters

#### Streaming API (Primary - Used in WebSocket)
- **max_tokens**: 4,096 tokens (line 611)
- **max_iterations**: 3 iterations per query
- **Temperature**: Not explicitly set (uses default)
- **Streaming**: Yes (real-time token-by-token)

#### Synchronous API (Fallback - HTTP endpoint)
- **max_tokens**: 8,192 tokens (line 866)
- **max_iterations**: 3 iterations per query

### System Prompt
- **Size**: ~4,000+ tokens (approximately 400 lines of detailed instructions)
- **Content**: Comprehensive task management rules, tool usage guidelines, date inference, navigation logic
- **Location**: Lines 39-464 in `orchestrator.py`

### Conversation History
- **History Loaded**: Last 5 messages (line 466)
- **Scope**: Global (no session filtering)
- **Format**: Includes tool calls and tool results in Anthropic's required format

### Tools Available
The agent has access to 10+ tools defined in `backend/app/agent/tools.py`:
1. `create_multiple_tasks` - Bulk task creation
2. `update_multiple_tasks` - Bulk task updates
3. `delete_multiple_tasks` - Bulk task deletion
4. `create_task` - Single task creation
5. `update_task` - Single task update
6. `delete_task` - Single task deletion
7. `list_tasks` - List tasks with filters
8. `search_tasks` - Semantic task search
9. `change_ui_view` - UI navigation control
10. `show_choices` - Modal choice display
11. `load_full_history` - Intelligent conversation history search

Each tool definition adds to the input token count (estimated ~500-1000 tokens for all tool definitions).

---

## Cost Analysis

### Anthropic Claude Sonnet 4.5 Pricing
**Note**: Pricing should be verified from Anthropic's official pricing page. Based on standard Claude pricing:

- **Input tokens**: ~$3.00 per million tokens
- **Output tokens**: ~$15.00 per million tokens

### Per-Query Token Estimation

#### Input Tokens (per query):
1. **System Prompt**: ~4,000 tokens
2. **Tool Definitions**: ~800 tokens (10+ tools with schemas)
3. **Conversation History**: ~500-2,000 tokens (last 5 messages, varies by context)
4. **Current User Query**: ~10-50 tokens (typical voice command)
5. **Total Input per Query**: ~5,300 - 6,850 tokens

#### Output Tokens (per query):
- **Typical Response**: 20-100 tokens (concise voice responses)
- **With Tool Calls**: 50-200 tokens (tool call JSON + response)
- **Complex Operations**: 100-500 tokens (bulk operations, planning)
- **Average Output**: ~100 tokens per query

#### Iterations:
- Most queries complete in **1 iteration** (single-turn with tools + response)
- Complex queries may use **2-3 iterations** (tool execution → follow-up → final response)
- **Average**: 1.2 iterations per query

### Cost Per Query Calculation

#### Scenario 1: Simple Query (1 iteration)
- Input: 5,500 tokens
- Output: 50 tokens
- **Cost**: (5,500 × $3/1M) + (50 × $15/1M) = **$0.0165 + $0.00075 = $0.01725 per query**

#### Scenario 2: Average Query (1.2 iterations)
- Input: 5,500 tokens × 1.2 = 6,600 tokens
- Output: 100 tokens × 1.2 = 120 tokens
- **Cost**: (6,600 × $3/1M) + (120 × $15/1M) = **$0.0198 + $0.0018 = $0.0216 per query**

#### Scenario 3: Complex Query (2 iterations)
- Input: 5,500 tokens × 2 = 11,000 tokens
- Output: 200 tokens × 2 = 400 tokens
- **Cost**: (11,000 × $3/1M) + (400 × $15/1M) = **$0.033 + $0.006 = $0.039 per query**

### Monthly Cost Estimates

#### Light Usage (100 queries/day = 3,000/month)
- Average cost per query: $0.0216
- **Monthly Cost**: 3,000 × $0.0216 = **$64.80/month**

#### Moderate Usage (500 queries/day = 15,000/month)
- Average cost per query: $0.0216
- **Monthly Cost**: 15,000 × $0.0216 = **$324/month**

#### Heavy Usage (2,000 queries/day = 60,000/month)
- Average cost per query: $0.0216
- **Monthly Cost**: 60,000 × $0.0216 = **$1,296/month**

#### Enterprise Usage (10,000 queries/day = 300,000/month)
- Average cost per query: $0.0216
- **Monthly Cost**: 300,000 × $0.0216 = **$6,480/month**

---

## Cost Optimization Opportunities

### 1. System Prompt Optimization
- **Current**: ~4,000 tokens
- **Potential Savings**: Reduce to ~2,500 tokens (37.5% reduction)
- **Impact**: Save ~$0.0045 per query (21% cost reduction)

### 2. Conversation History
- **Current**: Last 5 messages (global)
- **Optimization**: Reduce to last 3 messages or implement session-based filtering
- **Impact**: Save ~$0.002 per query (9% cost reduction)

### 3. Tool Definition Optimization
- **Current**: Full schemas for all tools
- **Optimization**: Only include tools likely to be used
- **Impact**: Minimal (tools are necessary for functionality)

### 4. Max Tokens Adjustment
- **Current**: 4,096 tokens (streaming), 8,192 tokens (sync)
- **Note**: Max tokens is a limit, not actual usage
- **Impact**: No direct cost impact (only affects if responses hit limit)

### 5. Caching
- Cache common queries/responses
- Cache system prompt (already done via instance variable)
- **Impact**: Could reduce redundant API calls

---

## Architecture Notes

### Orchestration Flow
1. **WebSocket Connection** → `backend/app/api/routes/agent.py`
2. **Audio Transcription** → Deepgram FLUX (separate cost)
3. **Query Processing** → `TaskAgent.process_query()` in `orchestrator.py`
4. **Claude API Call** → Streaming with tool calling
5. **Tool Execution** → Local database operations (no API cost)
6. **Response Streaming** → Real-time token-by-token to frontend

### Key Features
- **Streaming**: Real-time response generation
- **Tool Calling**: Native Anthropic tool calling support
- **Multi-iteration**: Up to 3 iterations for complex operations
- **Error Handling**: Graceful degradation on failures
- **History Management**: Automatic conversation history loading

### Performance Characteristics
- **Latency**: 2-5 seconds for typical queries (from README)
- **Reliability**: >95% tool call accuracy (from README)
- **Throughput**: Limited by Anthropic API rate limits

---

## Recommendations

1. **Monitor Actual Usage**: Track input/output tokens per query to refine estimates
2. **Implement Usage Analytics**: Log token counts for cost tracking
3. **Consider Rate Limiting**: Prevent abuse and control costs
4. **Optimize System Prompt**: Review and condense where possible
5. **Implement Caching**: Cache frequent queries to reduce API calls
6. **Set Budget Alerts**: Configure Anthropic dashboard alerts for cost thresholds

---

## Additional Costs

### Deepgram FLUX (Speech-to-Text)
- **Model**: `flux-general-en`
- **Cost**: Separate from Claude (not analyzed here)
- **Usage**: Real-time audio transcription

### Infrastructure
- **Database**: SQLite (no additional cost)
- **Server**: FastAPI backend hosting costs
- **WebSocket**: Connection management overhead

---

## Verification Steps

1. **Check Anthropic Dashboard**: Verify actual pricing for `claude-sonnet-4-20250514`
2. **Monitor API Usage**: Track actual token counts in production
3. **Review Billing**: Compare estimates with actual costs
4. **Optimize Based on Data**: Use real usage data to refine estimates

---

**Last Updated**: Based on codebase analysis as of current date
**Model Version**: `claude-sonnet-4-20250514`
**Pricing Source**: Estimated based on standard Claude pricing (verify with Anthropic)

