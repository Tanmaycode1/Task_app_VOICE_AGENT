# Todoist - Voice Agent Task Manager

This project is a real-time, voice-first task manager where the AI agent does more than answer questions. It takes actions, updates data, and controls the interface while the conversation is happening. The goal was to build something that feels like operating software through a human assistant, not filling a form through voice.

I built this as a complete agentic loop: live audio in, live UI updates out. The browser captures microphone audio and streams it to the backend. The backend proxies that stream to Deepgram FLUX for transcription and end-of-turn detection. As soon as a turn ends, the transcript is sent to the agent orchestrator. The orchestrator decides whether to call task tools, whether to change the UI, and what to say back. The frontend consumes those streaming events immediately, updates state, and speaks the final response through TTS.

The most important design decision is that the agent can directly influence interface state through structured commands, not by pretending with text. Tools on the backend return `ui_command` payloads such as `change_view` and `show_choices`. The frontend listens for these tool results and maps them to React state transitions. This is what enables real "agentic UI" behavior: your voice intent becomes actual screen state without extra clicks.

This app uses WebSockets for realtime communication. SSE is not used in this implementation. The `/api/agent` socket is multiplexed and carries both directions: audio chunks flowing up from the browser and streamed events flowing down from the backend. The `/api/flux` socket is the lower-level Deepgram proxy path and is useful when isolating transcription behavior from the full agent loop.

The streamed event model is intentionally explicit. You see phases like `thinking`, `tool_use_start`, `tool_use`, `tool_result`, progressive `text`, and final `done`. That event contract makes the UI feel trustworthy because users can watch what the system is doing in real time instead of waiting on a blank screen.

## Architecture and Technical Choices

The frontend is built with Next.js + React + Tailwind. The backend is FastAPI with SQLAlchemy and SQLite. Deepgram FLUX handles speech-to-text and turn detection, while Gemini (`google-genai`) handles tool-calling orchestration. Browser `SpeechSynthesis` is used for low-latency TTS output with zero extra backend service.

I intentionally kept orchestration logic in Python on the backend so tool execution and domain state stay close together. The orchestrator emits a clear stream of events, and the frontend remains a deterministic renderer of those events. This separation keeps the UI simple while still enabling complex voice flows.

The agent tools cover task CRUD, search/filter operations, bulk operations, history loading, and UI commands. That makes it possible to handle commands like "move all urgent tasks to next week and show me the week view" in one continuous conversation loop.

## Product Behavior That Matters

This app handles practical details that usually break voice demos. Mic capture is paused while TTS is speaking to avoid self-feedback loops. Agent responses stay visible until speech playback actually finishes, rather than disappearing on an arbitrary timeout. Ambiguous operations can open explicit choice modals, so destructive actions are controlled without killing conversational speed. There is also a keyboard-friendly mic toggle via spacebar (outside input fields), which makes testing and daily use much faster.

For reliability, websocket setup and proxy failures are handled with retries and defensive cleanup. If one side of the stream drops, the app exits the current loop cleanly instead of getting stuck in a half-open state.

## What This Demonstrates

This project demonstrates end-to-end agent integration in a real UI, not just model calls. It shows how to combine speech streaming, function/tool calling, event-driven rendering, and stateful UX into one coherent product. It also demonstrates the difference between "chat about tasks" and "operate task software through an agent."

## Quick Start

Backend setup:

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

Frontend setup:

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

Open `http://localhost:3000` and test with natural commands like "Add a task for tomorrow", "Move that meeting to next week", "Delete the compliance task", or "Show urgent tasks for Friday."

If you want to verify the architecture while testing, watch backend logs and you'll see the realtime loop clearly: Deepgram turn events, agent tool calls, tool results, streamed text, and final completion.

## Command Examples

| Say this | Agent action |
|---|---|
| "Add a task to prepare interview notes tomorrow at 10 AM" | Creates a task with scheduled date/time and confirms creation. |
| "Move the interview prep task to next week" | Finds matching task, updates schedule, and navigates to relevant view. |
| "Mark the interview prep task as complete" | Updates task status to completed and confirms. |
| "Delete the compliance task" | Finds and deletes the matching task; asks for choice if multiple matches exist. |
| "Show urgent tasks" | Switches to list view and applies urgent priority filtering. |
| "Show my tasks for Friday" | Lists Friday tasks, narrates them, and navigates to Friday view. |
| "What options did you show?" | Uses history lookup and explains previously shown choices. |
| "Undo last delete" | Loads relevant history, restores deleted task state, and confirms restore. |
