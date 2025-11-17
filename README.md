# Shram.ai - Voice-Controlled Task Manager

**An AI-powered task management system with natural language voice commands and intelligent UI control.**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Vercel-black?style=for-the-badge&logo=vercel)](https://task-app-voice-agent.vercel.app/)
[![Backend Status](https://img.shields.io/badge/Backend-Render-46E3B7?style=for-the-badge&logo=render)](https://task-app-voice-agent.onrender.com/api/health)

---

## 🚀 Live Demo

**Frontend:** [https://task-app-voice-agent.vercel.app/](https://task-app-voice-agent.vercel.app/)

**Backend Health Check:** [https://task-app-voice-agent.onrender.com/api/health](https://task-app-voice-agent.onrender.com/api/health)

> ⚠️ **Important:** The backend is deployed on Render.com's free tier, which has limited resources and may spin down after inactivity. If the app doesn't respond immediately, please wait 30-60 seconds for the backend to wake up. Check the health endpoint above to verify the API is running.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Sample Voice Commands](#sample-voice-commands)
- [Technology Stack](#technology-stack)
- [Architecture](#architecture)
- [Setup & Installation](#setup--installation)
- [Technical Deep Dives](#technical-deep-dives)
- [Known Limitations](#known-limitations)
- [Contributing](#contributing)

---

## 🎯 Overview

Shram.ai is a next-generation task management application that lets you control everything with your voice. No typing, no clicking through menus—just speak naturally, and the AI agent handles the rest.

### What Makes It Special?

**🎤 Voice-First Interface**
- Real-time speech-to-text with turn detection
- Natural language understanding for all commands
- Text-to-speech responses for hands-free operation
- Voice interruption support for natural conversations

**🤖 Intelligent AI Agent**
- Powered by Claude Sonnet 4.5 for reliable task operations
- Contextual understanding ("push that meeting to next week")
- Automatic bulk operations (create/update/delete multiple tasks)
- Conversation history for follow-up commands

**🎨 Agentic GUI (AGUI)**
- AI agent directly controls the user interface
- Automatic view switching based on voice commands
- Smart navigation to relevant dates after updates
- Dynamic filters and sorting through voice

**📅 Multiple View Modes**
- Daily view with hourly breakdown
- Weekly view with 7-day grid
- Monthly calendar view
- List view with advanced filtering and sorting

---

## ✨ Key Features

### 1. Natural Language Task Management
Create, update, and delete tasks using conversational language. The AI understands context and infers details like priority and deadlines from your phrasing.

### 2. Voice-Controlled UI Navigation
The AI agent directly controls the interface—switching views, applying filters, and navigating to dates based on your voice commands. No clicking required.

### 3. Smart Search & Display
Search results are visually displayed in the UI with a dedicated search banner, making it easy to see exactly what the agent found.

### 4. Bulk Operations
Perform actions on multiple tasks simultaneously—create several tasks at once, update all deadlines, or delete groups of tasks with a single command.

### 5. Automatic Date Navigation
When you reschedule tasks, the UI automatically jumps to show the new date in the appropriate view (daily/weekly/monthly).

### 6. Context-Aware Commands
The agent remembers your last 2 interactions, allowing follow-up commands like "make it urgent" after creating a task.

---

## 🎙️ Sample Voice Commands

### Creating Tasks

| Say This | What Happens |
|----------|--------------|
| "Add a task to review the quarterly financial report by this Friday at 3 PM" | Creates task with title, deadline (Friday 3 PM), default medium priority |
| "I need to call the dentist tomorrow morning" | Creates task for tomorrow at 12 PM (default time) |
| "Create an urgent task for fixing the production database connection error" | Creates high-priority task with inferred urgency |
| "Make me a task to prepare slides for the client presentation next Monday" | Creates task for next Monday at 12 PM |
| "Add a task to buy groceries" | Creates simple task with no deadline |

### Updating Tasks

| Say This | What Happens |
|----------|--------------|
| "Push the deployment task to next Wednesday" | Finds task about deployment, updates deadline to next Wednesday, keeps original time |
| "Move the client meeting to Monday" | Reschedules to nearest upcoming Monday, navigates to that date in calendar |
| "Mark the quarterly report as complete" | Updates task status to completed |
| "Change the presentation task to high priority" | Updates priority level |
| "Reschedule the database backup to next Friday at 11 PM" | Updates deadline with specific time |

### Deleting Tasks

| Say This | What Happens |
|----------|--------------|
| "Delete the task about the old marketing campaign" | Searches for matching task, deletes if one clear match found |
| "Remove the third task from the list" | Deletes task at position 3 in current view |
| "Cancel that compliance audit task" | Searches and removes matching task |
| "Delete all meeting-related tasks" | Bulk deletes all tasks matching "meeting" |

### Navigation & View Control

| Say This | What Happens |
|----------|--------------|
| "Show me all tasks for December" | Switches to monthly view, displays December 2025 |
| "Take me to next week" | Opens weekly view showing next 7 days |
| "Go to November twenty-fifth" | Opens daily view for Nov 25, 2025 |
| "Show all my tasks in a list" | Switches to list view with all tasks |
| "Show me this Friday" | Opens daily view for this coming Friday |

### Search & Filtering

| Say This | What Happens |
|----------|--------------|
| "Show me all administrative tasks" | Searches tasks for "administrative", displays results in list view with search banner |
| "What urgent tasks do I have?" | Filters list view to show only urgent priority tasks |
| "Show tasks sorted by deadline ascending" | Switches to list view, sorts by deadline (earliest first) |
| "Show me completed tasks" | Filters to display only completed tasks |
| "Find tasks related to the client presentation" | Searches and displays all matching tasks |

### Context-Aware Follow-Ups

| Conversation Flow | What Happens |
|-------------------|--------------|
| **You:** "Add a task for the board presentation"<br>**Agent:** "Done"<br>**You:** "Make it urgent" | Agent remembers the presentation task and updates its priority to urgent |
| **You:** "Show me tasks for next week"<br>**Agent:** "Showing next week"<br>**You:** "Push them all to the following week" | Agent bulk-updates all displayed tasks by +7 days |
| **You:** "Delete the compliance task"<br>**Agent:** "Deleted"<br>**You:** "Create a new one for next month" | Agent creates new compliance task with deadline in next month |

---

## 🛠️ Technology Stack

### Why Deepgram FLUX?

We chose Deepgram's FLUX model for speech-to-text after evaluating multiple solutions:

**✅ Real-Time Turn Detection**
FLUX has built-in end-of-turn detection with configurable thresholds. When you finish speaking, the system knows immediately and starts processing—no awkward waiting for silence. This is critical for natural voice interactions.

**✅ Streaming Architecture**
FLUX streams transcriptions as you speak, not after you're done. This means lower perceived latency—the agent can start thinking while you're still talking. In practice, this saves 1-2 seconds per query.

**✅ WebSocket-Based Communication**
Everything happens over WebSocket connections for bidirectional real-time streaming. Your browser captures audio, sends it to our FastAPI backend, which proxies to Deepgram via another WebSocket. Results stream back through the same pipeline instantly.

**✅ High Accuracy**
The `flux-general-en` model provides excellent accuracy for general English speech with various accents and speaking styles.

### Why Claude Sonnet 4.5?

Anthropic's Claude Sonnet 4.5 powers the task management agent:

**✅ Reliable Tool Calling**
Sonnet 4.5 has exceptional function calling capabilities. We've defined 10+ tools (create_task, update_task, delete_task, search_tasks, etc.) and the model consistently calls them with correct parameters. Tool call reliability is >95% in production.

**✅ Streaming Support**
The model streams responses token-by-token AND streams tool calls as they happen. This enables real-time feedback: "thinking...", "creating task...", "completed!". The agent feels responsive and alive.

**✅ Natural Language Understanding**
Sonnet 4.5 handles ambiguous queries exceptionally well. Say "delete that compliance thing" and it searches your tasks, finds the match, and deletes it. No rigid command syntax required.

**✅ Context Window & Memory**
With a large context window, we include conversation history (last 2 turns) so the agent remembers recent context. Fast inference means most queries complete in 2-5 seconds end-to-end.

**✅ Bulk Operation Support**
With increased token limits (2048 tokens), the model can handle complex bulk operations involving multiple tasks efficiently.

### Tech Stack Summary

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Frontend** | Next.js 16 + React 19 | Modern web interface with SSR |
| **Backend** | FastAPI + Python 3.11 | High-performance async API |
| **Speech-to-Text** | Deepgram FLUX | Real-time voice transcription |
| **AI Agent** | Claude Sonnet 4.5 | Natural language understanding |
| **Database** | SQLite + SQLAlchemy | Task and conversation storage |
| **Text-to-Speech** | Web Speech API | Browser-native voice output |
| **Styling** | Tailwind CSS v4 | Utility-first styling |
| **Deployment** | Vercel + Render.com | Frontend + Backend hosting |

---

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js)                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  AgentVoiceButton Component                              │   │
│  │  • Captures mic audio (Web Audio API)                    │   │
│  │  • Converts to PCM16 format                              │   │
│  │  • Streams to backend via WebSocket                      │   │
│  │  • Displays transcripts & agent responses                │   │
│  │  • Text-to-Speech for agent replies                      │   │
│  │  • Handles UI commands from agent                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                             │                                   │
│                             │ WebSocket                         │
│                             ▼                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Agent WebSocket Handler (/api/agent)                    │   │
│  │  • Receives audio stream from frontend                   │   │
│  │  • Forwards to Deepgram FLUX via WebSocket               │   │
│  │  • On turn detection → triggers agent                    │   │
│  │  • Streams agent events back to frontend                 │   │
│  │  • Auto-retry on failures (2 attempts)                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                             │                                   │
│                             ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Task Agent (orchestrator.py)                            │   │
│  │  • Loads conversation history (last 2 turns)             │   │
│  │  • Streams query to Claude Sonnet 4.5                    │   │
│  │  • Executes tool calls (CRUD operations)                 │   │
│  │  • Yields events: thinking, tool_use, text, done         │   │
│  │  • Max 3 iterations, 2048 token limit                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                             │                                   │
│                             ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Tools (tools.py)                                        │   │
│  │  • create_task / create_multiple_tasks                   │   │
│  │  • update_task / update_multiple_tasks                   │   │
│  │  • delete_task / delete_multiple_tasks                   │   │
│  │  • list_tasks / search_tasks / get_task_stats            │   │
│  │  • change_ui_view (sends UI commands)                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                             │                                   │
│                             ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  SQLite Database                                         │   │
│  │  • Tasks table (id, title, deadline, priority, etc.)     │   │
│  │  • ConversationMessage table (for history)               │   │
│  └──────────────────────────────────────────────────────────┘   │
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

### WebSocket Flow

1. **User clicks voice button** → Frontend opens WebSocket to `/api/agent`
2. **Mic starts capturing** → Audio processed via Web Audio API
3. **Audio encoding** → Float32 samples → Int16 PCM (Linear16 format)
4. **Streaming to backend** → Chunks of audio sent via WebSocket
5. **Backend proxy** → FastAPI forwards audio to Deepgram FLUX
6. **FLUX transcribes** → Streams back partial transcripts and turn events
7. **Turn detection** → When FLUX detects "EndOfTurn", backend triggers agent
8. **Agent processing** → Claude streams thinking, tool calls, results
9. **Events forwarded** → All agent events streamed back to frontend
10. **UI updates** → Frontend displays progress + speaks response via TTS

### Agentic GUI (AGUI)

The AI agent can directly control the frontend UI through `ui_command` objects:

```python
# Example: Agent wants to show December monthly view
{
  "type": "change_view",
  "view_mode": "monthly",
  "target_date": "2025-12-01"
}

# Example: Agent wants to show search results
{
  "type": "change_view",
  "view_mode": "list",
  "search_results": [1, 3, 7],
  "search_query": "administrative"
}

# Example: Agent wants to apply filters
{
  "type": "change_view",
  "view_mode": "list",
  "filter_priority": "urgent",
  "sort_by": "deadline",
  "sort_order": "asc"
}
```

The frontend's `handleUICommand` function receives these commands and updates React state accordingly, enabling true voice-controlled UI navigation.

---

## 📦 Setup & Installation

### Prerequisites

- Python 3.11+
- Node.js 25+ (specified in package.json)
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
NEXT_PUBLIC_API_BASE=http://localhost:8000/api
NEXT_PUBLIC_AGENT_WS_URL=ws://localhost:8000/api/agent
EOL

# Start development server
npm run dev
```

Navigate to `http://localhost:3000` and start using voice commands!

---

## 🔍 Technical Deep Dives

### Speech-to-Text Pipeline

The STT pipeline uses Deepgram FLUX with optimized parameters:

```javascript
model: 'flux-general-en'        // General English model
sample_rate: 16000              // 16kHz audio
encoding: 'linear16'            // PCM 16-bit signed little-endian
eot_threshold: 0.9              // End-of-turn confidence (90%)
```

Audio capture uses Web Audio API with echo cancellation:

```javascript
audio: {
  channelCount: 1,
  sampleRate: 16000,
  echoCancellation: true,      // Prevents TTS feedback
  noiseSuppression: true,       // Reduces background noise
  autoGainControl: true,        // Normalizes volume
}
```

Audio processing:
1. Read Float32 samples from input buffer
2. Clamp values to [-1, 1] range
3. Convert to Int16 (multiply by 32767)
4. Send as binary WebSocket frames

### Agent Orchestration

The agent follows a multi-iteration loop (max 3 iterations):

1. **Load Context:** Retrieve last 2 conversation turns from database
2. **Add Query:** Append current user query to messages
3. **Stream to Claude:** Send messages + tool definitions to Sonnet 4.5
4. **Process Stream:**
   - Text content → Forward to frontend for display + TTS
   - Tool call → Execute function, add result to messages
5. **Iterate if Needed:** If tool was called, go back to step 3
6. **Finalize:** Yield "done" event, save conversation to database

This enables complex multi-step operations like:
- Search for tasks → Delete matching ones → Confirm deletion

All in a single voice command.

### Text-to-Speech

Using browser-native `SpeechSynthesis` API:
- Zero latency (no API calls)
- Works offline
- No additional cost
- Voice selection prioritizes female US/UK/AU English voices

Mic is automatically muted during TTS to prevent feedback loops:

```javascript
processor.onaudioprocess = (event) => {
  if (isSpeakingRef.current) return;  // Mute during TTS
  // Process and send audio
}
```

### Auto-Retry & Error Recovery

- **Deepgram Connection:** 3 retry attempts with 500ms delay
- **Agent Processing:** 2 retry attempts with 30-second timeout
- **Error Handling:** Corrupted conversation history is cleared automatically
- **State Reset:** Frontend resets cleanly after errors for immediate retry

---

## ⚠️ Known Limitations

1. **Browser Compatibility:** TTS quality varies across browsers. Chrome/Edge recommended.
2. **Microphone Required:** Voice features require microphone permissions.
3. **English Only:** FLUX is configured for English (can be adapted for other languages).
4. **API Rate Limits:** Free tier limits apply for Deepgram and Anthropic APIs.
5. **Context Window:** Only last 2 conversation turns retained for low latency.
6. **Free Tier Hosting:** Backend on Render.com free tier may sleep after inactivity.

---

## 🚧 Future Improvements

- [ ] Calendar integration (Google Calendar, Outlook)
- [ ] Multi-language support (Spanish, French, Hindi)
- [ ] Mobile app (React Native)
- [ ] Collaborative task boards (multi-user)
- [ ] Voice biometrics for authentication
- [ ] Offline mode with local STT model
- [ ] Custom wake word ("Hey Shram")
- [ ] Recurring tasks support
- [ ] Task templates and automation
- [ ] Export to PDF/CSV



## 🙏 Acknowledgments

- **Deepgram** for the exceptional FLUX speech-to-text model
- **Anthropic** for Claude Sonnet 4.5 and excellent API documentation
- **Next.js** and **FastAPI** teams for powerful frameworks
- The open-source community for tools and inspiration
