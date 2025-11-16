# AI Agent Setup Guide

## Complete Agent Implementation

The agent system is now fully integrated with conversation history persistence.

### Features

1. **Conversation History**
   - All conversations saved to SQLite (`conversation_messages` table)
   - Persistent across sessions
   - Session-based tracking with unique session IDs
   - Automatically loaded before each query

2. **Agent Capabilities**
   - Create tasks from voice commands
   - Update existing tasks (deadline, priority, status, etc.)
   - Delete tasks
   - List and search tasks
   - Get task statistics
   - **Control UI view and date selection**
   - Natural language understanding with current date/time context

3. **Streaming Architecture**
   - Real-time FLUX turn detection
   - Agent processes on EndOfTurn event
   - Streaming tool execution updates
   - Final response streaming

### Setup

1. **Install dependencies**:
```bash
cd backend
pip install -r requirements.txt
```

2. **Set environment variables**:
```bash
export DEEPGRAM_API_KEY="your_deepgram_api_key"
export ANTHROPIC_API_KEY="your_anthropic_api_key"
```

3. **Start backend** (this will auto-create the conversation table):
```bash
uvicorn app.main:app --reload --port 8000
```

4. **Start frontend**:
```bash
cd frontend
npm run dev
```

### How It Works

1. User clicks voice button → opens WebSocket to `/api/agent`
2. Audio streams to Deepgram FLUX for transcription
3. On `EndOfTurn` event, transcript is sent to agent
4. Agent:
   - Loads last 20 messages from database for context
   - Saves user query to database
   - Processes with Claude Sonnet 4.5
   - Uses tools to manage tasks
   - Streams responses back
   - Saves assistant response to database
5. UI displays real-time updates and auto-refreshes tasks

### Database Schema

**conversation_messages table:**
- `id`: Primary key
- `session_id`: UUID for grouping conversations
- `role`: "user" or "assistant"
- `content`: Message text
- `tool_calls`: JSON array of tool invocations (optional)
- `tool_results`: JSON array of tool results (optional)
- `created_at`: Timestamp

### Example Voice Commands

**Task Management:**
- "Create a high priority task to review the PR tomorrow at 2 PM"
- "Show me all my urgent tasks"
- "Change task 5's deadline to next Friday"
- "Mark all completed tasks as done"
- "Delete the meeting task"
- "What tasks do I have this week?"

**UI Control:**
- "Show me tasks for December" → Switches to monthly view for December
- "What's happening next week?" → Switches to weekly view for next week
- "Show me today's tasks" → Switches to daily view for today
- "Switch to list view" → Changes to list view
- "Show me tasks in January" → Monthly view for January 2025

### Session Management

Each WebSocket connection can optionally pass a `session_id` query parameter:
```
ws://localhost:8000/api/agent?session_id=abc123&model=flux-general-en&...
```

If not provided, a new UUID is generated. This allows:
- Continuing conversations across reconnections
- Multiple users with separate histories
- Testing different conversation contexts

### Debugging

Check the backend logs for:
- "Agent websocket client connected"
- "Connected to Deepgram FLUX"
- "EndOfTurn detected, processing: [transcript]"
- Tool execution logs
- Database save confirmations

Check the frontend console for:
- WebSocket connection status
- FLUX events (transcripts, turn info)
- Agent events (tool use, responses)
- Any errors

