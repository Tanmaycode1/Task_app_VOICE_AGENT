# Shram.ai - AI-Powered Voice Task Manager

> Because typing out tasks is so 2020. Just talk, and let AI handle the rest.

## What is this?

Shram.ai is a task management app that you can literally *talk to*. No more fumbling with keyboards or clicking through menus - just speak naturally like you're telling a friend what you need to do, and the AI agent figures it out. Want to add a task for tomorrow? Say it. Need to see what's on your plate for December? Ask. It's that simple.

The cool part? It actually understands context. You can say "push that meeting task to next week" and it knows exactly what you mean. Plus it talks back to you (using text-to-speech), so you get instant confirmation without even looking at the screen.

## Why We Built It This Way

### The Voice Stack: Deepgram FLUX

We tried a bunch of speech-to-text solutions before landing on Deepgram's FLUX model, and honestly? It's kind of perfect for this use case. Here's why:

**Turn Detection That Actually Works**
Most STT systems just transcribe continuously and leave you to figure out when someone stopped talking. FLUX has built-in turn detection with configurable thresholds, so it knows when you've finished your sentence. This is *huge* for a voice agent because the system can immediately start processing your request instead of waiting awkwardly for silence.

**Streaming Architecture**
FLUX streams results as you speak, not after you're done. This means lower latency - the agent can start thinking about your request while you're still talking. In practice, this shaves off like 1-2 seconds from the response time, which makes the whole experience feel way more natural.

**WebSocket-Based Real-Time Communication**
We're using WebSocket connections for bidirectional streaming. Your browser captures audio, sends it to our FastAPI backend, which proxies it to Deepgram via another WebSocket. Results stream back through the same pipeline. It's like a phone call but for AI agents.

### The Brain: Claude Sonnet 4.5

For the AI agent that actually understands your commands and manipulates tasks, we went with Anthropic's Claude Sonnet 4.5. After experimenting with a few models, this one just hit different:

**Tool Calling That's Actually Reliable**
Sonnet 4.5 has really solid function calling capabilities. You can define tools (functions) like `create_task`, `update_task`, `delete_task`, and the model consistently calls them with the right parameters. We've got like 7 different tools and it rarely messes up the invocations.

**Streaming Support**
The model streams its responses token-by-token AND streams tool calls as they happen. This means we can show you "thinking...", "creating task...", "completed!" in real-time. Makes the agent feel more alive and less like a loading spinner.

**Context Window & Speed**
With a large context window, we can include conversation history (last 2 turns) so the agent remembers what you just talked about. And it's fast enough that most queries complete in 2-5 seconds end-to-end, including the speech recognition time.

**Natural Language Understanding**
This is the real kicker - Sonnet 4.5 handles ambiguous queries really well. Say "delete that compliance thing" and it'll search your tasks, find the one about compliance, and delete it. No need for precise command syntax.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js)                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  AgentVoiceButton Component                              │  │
│  │  • Captures mic audio (Web Audio API)                   │  │
│  │  • Converts to PCM16 format                             │  │
│  │  • Streams to backend via WebSocket                     │  │
│  │  • Displays transcripts & agent responses               │  │
│  │  • Text-to-Speech for agent replies                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                             │                                    │
│                             │ WebSocket                          │
│                             ▼                                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Agent WebSocket Handler (/api/agent)                   │  │
│  │  • Receives audio stream from frontend                  │  │
│  │  • Forwards to Deepgram FLUX via WS                     │  │
│  │  • On turn detection → triggers agent                   │  │
│  │  • Streams agent events back to frontend                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                             │                                    │
│                             ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Task Agent (orchestrator.py)                           │  │
│  │  • Loads conversation history (last 2 turns)            │  │
│  │  • Streams query to Claude Sonnet 4.5                   │  │
│  │  • Executes tool calls (CRUD operations)                │  │
│  │  • Yields events: thinking, tool_use, text, done        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                             │                                    │
│                             ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Tools (tools.py)                                        │  │
│  │  • create_task    • update_task    • delete_task        │  │
│  │  • list_tasks     • search_tasks   • get_task_stats     │  │
│  │  • change_ui_view (sends UI commands to frontend)       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                             │                                    │
│                             ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  SQLite Database                                         │  │
│  │  • Tasks table (id, title, deadline, priority, etc.)    │  │
│  │  • ConversationMessage table (for history)              │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

        ▲                                    ▲
        │                                    │
        │ REST APIs                          │ WebSocket
        │                                    │
        ▼                                    ▼
┌──────────────────┐              ┌──────────────────┐
│  Deepgram FLUX   │              │  Anthropic API   │
│  (Speech-to-Text)│              │  (Claude LLM)    │
└──────────────────┘              └──────────────────┘
```

### How the WebSocket Flow Works

1. **User clicks voice button** → Frontend opens WebSocket to `/api/agent`
2. **Mic starts capturing** → Audio processed via Web Audio API's ScriptProcessorNode
3. **Audio encoding** → Float32 samples → Int16 PCM (Linear16 format)
4. **Streaming to backend** → Chunks of audio sent via WebSocket as binary frames
5. **Backend proxy** → FastAPI forwards audio to Deepgram FLUX via another WebSocket
6. **FLUX transcribes** → Streams back partial transcripts and turn events
7. **Turn detection** → When FLUX detects "EndOfTurn", backend triggers the agent
8. **Agent processing** → Claude streams back thinking, tool calls, results
9. **Events forwarded** → All agent events streamed back to frontend
10. **UI updates** → Frontend displays progress and speaks final response via TTS

The beauty of this setup is everything is real-time. There's no "record → upload → wait → download" cycle. It's all streaming, so the latency is minimal.

## The Frontend: View Modes & AGUI

The UI has four view modes, and here's where it gets interesting - the AI agent can control which view you're seeing. We call this **Agentic GUI (AGUI)**.

### View Modes

1. **Daily View** - Hour-by-hour breakdown of a single day
2. **Weekly View** - 7-day grid with tasks mapped to dates  
3. **Monthly View** - Calendar month view (like Google Calendar)
4. **List View** - Filterable, sortable table of all tasks

### How AGUI Works

When you say something like "show me December tasks", the agent:
1. Recognizes this is a navigation command (not a task operation)
2. Calls the `change_ui_view` tool with `view_mode="monthly"` and `target_date="2025-12-01"`
3. Returns a `ui_command` in the tool result
4. Backend sends this to frontend as part of the agent event
5. Frontend's `handleUICommand` function executes it
6. View switches to monthly December automatically

Similarly, if you say "show me urgent tasks sorted by deadline", the agent:
- Switches to list view
- Sets priority filter to "urgent"
- Sets sort field to "deadline"

All without you clicking anything. The agent literally controls the UI based on what you ask for.

### Search Results Display

When you search for tasks (like "show me administrative tasks"), we've got a special flow:
- Agent calls `search_tasks(query="administrative")`
- Tool returns matching task IDs
- Agent sends a UI command with `search_results=[1,2,3]` and `search_query="administrative"`
- Frontend switches to list view and filters to ONLY show those specific tasks
- Shows a blue banner: "Search results for 'administrative' (3 tasks found)"

This way the UI visually confirms what the agent found, instead of just speaking it.

## Code Structure

```
shram.ai/
├── backend/
│   ├── app/
│   │   ├── agent/
│   │   │   ├── orchestrator.py      # Claude agent with streaming
│   │   │   └── tools.py             # Tool definitions & implementations
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── agent.py         # WebSocket handler for voice agent
│   │   │       ├── tasks.py         # REST API for CRUD operations
│   │   │       └── flux.py          # Deepgram FLUX proxy (optional)
│   │   ├── models/
│   │   │   ├── task.py              # SQLAlchemy Task model
│   │   │   └── conversation.py      # Conversation history model
│   │   ├── db/
│   │   │   ├── base.py              # Database session config
│   │   │   └── init_db.py           # Table creation
│   │   └── main.py                  # FastAPI app entry point
│   ├── requirements.txt
│   └── shram.db                     # SQLite database file
│
└── frontend/
    ├── app/
    │   ├── page.tsx                 # Main page with all view modes
    │   └── layout.tsx               # Root layout
    ├── components/
    │   ├── AgentVoiceButton.tsx     # Voice UI component
    │   └── TaskModal.tsx            # Task details modal
    ├── lib/
    │   └── api.ts                   # API client functions
    └── package.json
```

## Key Features

### 1. Natural Language Task Creation

Just say what you want to do:
- "Add a task to review the quarterly report by next Friday"
- "I need to call mom tomorrow"  
- "Make me a task for the dentist appointment on December 15th"

The agent infers:
- **Title** from your description
- **Priority** from keywords (urgent, important, ASAP)
- **Deadline** from date/time expressions
- **Time** defaults to 12 PM if you don't specify

### 2. Contextual Updates & Deletes

No need to be precise:
- "Push that meeting to next week" - searches recent tasks, finds the meeting, updates it
- "Delete the task about compliance" - searches by keyword, deletes if one match
- "Mark the report task as complete" - updates status
- "Change the priority on that bug fix to urgent" - updates priority

### 3. Smart Search & Filtering

- "Show me all administrative tasks" → filters by keyword in title/description/notes
- "What urgent tasks do I have?" → filters by priority
- "Show tasks sorted by deadline" → sorts the list view
- "Take me to December" → switches to December monthly view

### 4. Voice Interruption

If the agent is talking (via TTS) and you start speaking, it immediately stops and starts listening. This makes conversations feel more natural - you can interrupt just like with a human.

### 5. Conversation History

The agent remembers your last 2 turns, so you can have contextual conversations:
- You: "Add a task for the presentation"
- Agent: "Done"  
- You: "Make it urgent" ← Agent knows you mean the presentation task

### 6. Auto-Retry & Error Recovery

If something fails (network issue, API timeout), the system:
- Retries once automatically
- Clears corrupted conversation history if needed
- Shows a friendly error message
- Resets state so you can try again immediately

## Sample Queries

### Task Creation
```
"Add a task to finish the backend API by Friday"
"I want to work on the presentation slides tomorrow"  
"Make me a task for the team meeting next Monday at 3 PM"
"Add an urgent task to fix the production bug"
```

### Task Updates
```
"Push the task about deployment to next week"
"Mark the report task as complete"
"Change the presentation priority to high"
"Move the meeting from tomorrow to Thursday"
```

### Task Deletion
```
"Delete the task about the old feature"
"Remove the 3rd task" (deletes by position in current view)
"Cancel that compliance task"
```

### Navigation & Views
```
"Show me December tasks"
"Take me to next week"
"Show all tasks sorted by priority"
"Show me tasks that are in progress"
"Go to November 25th"
```

### Search
```
"Show me all administrative tasks"
"Find tasks related to the client meeting"
"What tasks mention the new feature?"
```

## Setup & Installation

### Prerequisites
- Python 3.11+
- Node.js 18+
- Deepgram API key ([get one here](https://deepgram.com))
- Anthropic API key ([get one here](https://anthropic.com))

### Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOL
DEEPGRAM_API_KEY=your_deepgram_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
DATABASE_PATH=shram.db
EOL

# Initialize database
python -c "from app.db.init_db import init_db; init_db()"

# (Optional) Seed with sample data
python -c "from app.db.seed_data import seed_database; seed_database()"

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env.local file
cat > .env.local << EOL
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_AGENT_WS_URL=ws://localhost:8000/api/agent
EOL

# Start development server
npm run dev
```

Navigate to `http://localhost:3000` and you're good to go!

## Technical Deep Dives

### Speech-to-Text Pipeline

The STT pipeline uses Deepgram's FLUX model with these parameters:

```javascript
model: 'flux-general-en'        // General English model
sample_rate: 16000              // 16kHz audio
encoding: 'linear16'            // PCM 16-bit signed little-endian
eot_threshold: 0.9              // End-of-turn confidence (90%)
```

Audio is captured via Web Audio API's `getUserMedia`, processed through a `ScriptProcessorNode` that:
1. Reads Float32 samples from input buffer
2. Clamps values to [-1, 1] range
3. Converts to Int16 (multiply by 32767)
4. Sends as binary WebSocket frames

On the backend, we've got WebSocket echo cancellation enabled in the browser:
```javascript
audio: {
  echoCancellation: true,      // Prevents TTS from being re-captured
  noiseSuppression: true,       // Reduces background noise
  autoGainControl: true,        // Normalizes volume
}
```

### Text-to-Speech Implementation

We're using the browser's native `SpeechSynthesis` API (not a cloud service) because:
- Zero latency - no API calls needed
- Works offline
- No additional cost
- Pretty decent quality on modern browsers

The mic is muted during TTS playback to prevent feedback loops:
```javascript
processor.onaudioprocess = (event) => {
  if (isSpeakingRef.current) return;  // Don't send audio during TTS
  // ... process and send audio
}
```

### Agent Orchestration

The agent follows this loop:
1. Load last 2 conversation turns from database
2. Add current user query to messages
3. Stream query to Claude with tool definitions
4. For each streamed chunk:
   - If it's text content → forward to frontend (for display & TTS)
   - If it's a tool call → execute function, add result to messages
5. If tool was called → loop back to step 3 (max 3 iterations)
6. Yield "done" event
7. Save conversation to database

This multi-iteration approach lets the agent:
- Search for a task
- Then delete it based on the search results
- Then respond with confirmation

All in one query.

### CRUD Operations

All task operations return a consistent format:
```python
{
  "success": True/False,
  "message": "Human readable message",
  "task": { ... },  # Task object (if applicable)
  "ui_command": { ... }  # Optional UI control command
}
```

The `ui_command` field is how tools control the frontend. Example:
```python
{
  "type": "change_view",
  "view_mode": "monthly",
  "target_date": "2025-12-01"
}
```

Frontend's `handleUICommand` function parses this and updates React state accordingly.

## Known Limitations

1. **Browser Compatibility** - TTS quality varies. Chrome/Edge work best.
2. **Microphone Required** - Can't use voice features without mic access.
3. **English Only** - FLUX is configured for English; other languages need different model.
4. **Rate Limits** - Deepgram and Anthropic APIs have rate limits on free tiers.
5. **Context Window** - Only last 2 conversation turns remembered to keep latency low.

## Future Improvements

- [ ] Add calendar integration (Google Calendar, Outlook)
- [ ] Multi-language support
- [ ] Mobile app (React Native)
- [ ] Collaborative task boards (multiple users)
- [ ] Voice biometrics for authentication
- [ ] Offline mode with local STT model
- [ ] Custom wake word ("Hey Shram")
- [ ] Recurring tasks support

## Contributing

Found a bug? Have an idea? PRs are welcome!

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - feel free to use this for whatever you want.

## Acknowledgments

- Deepgram for the awesome FLUX model
- Anthropic for Claude Sonnet 4.5
- The Next.js and FastAPI teams for excellent frameworks
- Everyone who's built voice interfaces before us and shared their learnings

---

Built with ❤️ and way too much coffee by [@Tanmaycode1](https://github.com/Tanmaycode1)

**Questions? Issues?** Open an issue on GitHub or reach out!
