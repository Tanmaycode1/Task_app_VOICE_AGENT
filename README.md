# Todoist - Voice Copilot for Task Management

Todoist is a real-time, voice-first AI copilot for task management. It does three things in one loop: understands natural language, executes task operations, and controls the UI. The core experience is "speak once, see action instantly."

## Project Summary

This project is designed as an end-to-end agentic interface rather than a chat-only assistant. The user speaks naturally, audio is streamed live, the transcript is converted into tool calls, and the frontend updates immediately based on structured backend events. The result is a hands-free workflow for managing tasks, dates, priorities, and views.

## Core Capabilities

- Voice-driven task creation, update, deletion, and search.
- Agent-controlled UI navigation (`change_view`, `show_choices`).
- Real-time streaming feedback (`thinking`, tool activity, text response).
- Context-aware follow-ups and ambiguity handling.
- Browser-native TTS with feedback-loop prevention.

## Architecture

### Frontend

The frontend is built with Next.js, React, and Tailwind. It handles microphone capture, renders streaming agent state, applies UI commands, and speaks responses through the Web Speech API.

### Backend

The backend is FastAPI with SQLAlchemy and SQLite. It manages websocket streams, task tools, orchestration, and conversation persistence.

### AI + Speech Stack

- LLM orchestration: Gemini 2.5 Flash (`google-genai`)
- Speech-to-text: Deepgram FLUX
- Text-to-speech: Browser SpeechSynthesis API

## Realtime Communication Model

This project uses **WebSockets**, not SSE.

- `ws /api/agent`: full-duplex voice + agent event stream.
- `ws /api/flux`: Deepgram proxy path.

`/api/agent` carries both:
- Upstream: PCM16 audio chunks from browser to backend.
- Downstream: transcription and agent events back to the UI.

### Main Event Types

- Transport events: `flux_event`, `agent_start`, `agent_event`, `agent_error`
- Agent event payloads: `thinking`, `tool_use_start`, `tool_use`, `tool_result`, `text`, `done`

## How the Agent Controls UI

The agent does not directly mutate frontend components. Instead, backend tools return structured `ui_command` payloads. The frontend receives these commands from `tool_result` events and maps them to React state updates.

Typical commands:
- `change_view` for daily/weekly/monthly/list navigation and filters
- `show_choices` for ambiguity resolution and human-in-the-loop selection

This design keeps orchestration on the backend while keeping frontend rendering deterministic and maintainable.

## Product-Level Behavior

- Mic is muted while TTS is speaking to avoid self-capture.
- Agent response remains visible until speech playback completes.
- Spacebar toggles mic on/off (outside input fields).
- Retry and cleanup logic handles dropped websocket states safely.

## Quick Start

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env`:

```env
DEEPGRAM_API_KEY=your_deepgram_key
GEMINI_API_KEY=your_gemini_key
DATABASE_PATH=shram.db
```

Run backend:

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_BASE=http://localhost:8000/api
NEXT_PUBLIC_AGENT_WS_URL=ws://localhost:8000/api/agent
```

Run frontend:

```bash
npm run dev
```

Open `http://localhost:3000`.

## Command Examples

| Command | Outcome |
|---|---|
| "Add a task to prepare interview notes tomorrow at 10 AM" | Creates a scheduled task and confirms. |
| "Move the interview prep task to next week" | Finds match, updates schedule, navigates to relevant view. |
| "Mark the interview prep task complete" | Updates status to completed. |
| "Delete the compliance task" | Deletes a clear match or opens choices if ambiguous. |
| "Show urgent tasks" | Switches to list view with urgent filter. |
| "Show my tasks for Friday" | Narrates tasks and navigates to Friday view. |
| "What options did you show?" | Loads relevant history and summarizes prior choices. |
| "Undo last delete" | Restores deleted task state from conversation/tool history. |

## AI-Assisted Development Note

This project was built with strong AI assistance using Cursor. The initial backend and frontend scaffolding was generated through Cursor, and I iterated from there with my own product direction and orchestration logic. I used Cursor's auto model for development speed. Bug analysis and issue resolution were handled manually by me, while much of the implementation-heavy work (naming, formatting, code generation, and documentation drafting) was accelerated with Cursor.
