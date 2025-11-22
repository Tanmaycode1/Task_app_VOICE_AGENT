# Backend Architecture Analysis

## Executive Summary

This document provides a comprehensive analysis of the Shram.ai backend architecture, covering:
- **Database Connections**: SQLite (not Supabase) with SQLAlchemy ORM
- **Caching Implementation**: Minimal - only settings caching via `@lru_cache`
- **User Query Processing**: WebSocket-based streaming with Claude Sonnet 4.5
- **Session Management**: Global conversation history (no session isolation)
- **Connection Pooling**: SQLite with thread-safe connection handling

---

## 1. Database Architecture

### 1.1 Database Type: SQLite (Not Supabase)

**Important Note**: The backend uses **SQLite**, not Supabase. There are no Supabase connections in the codebase.

**Location**: `backend/app/db/base.py`

```python
# SQLite engine - creates file in backend directory
engine = create_engine(
    f"sqlite:///{settings.database_path}",
    connect_args={"check_same_thread": False},  # needed for SQLite
    echo=False,  # Disable SQL query logging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

**Key Characteristics**:
- **Database File**: `backend/shram.db` (default path)
- **Connection Mode**: Thread-safe (`check_same_thread=False`)
- **Logging**: SQLAlchemy engine logging suppressed (errors only)
- **Session Factory**: `SessionLocal` creates new sessions per request

### 1.2 Database Models

**Two Main Models**:

1. **Task Model** (`backend/app/models/task.py`):
   - Fields: `id`, `title`, `description`, `notes`, `priority`, `status`
   - Timestamps: `created_at`, `updated_at`, `scheduled_date`, `deadline`, `completed_at`
   - Table: `tasks`

2. **ConversationMessage Model** (`backend/app/models/conversation.py`):
   - Fields: `id`, `role`, `content`, `tool_calls`, `tool_results`, `created_at`
   - Table: `conversation_messages`
   - Stores: User queries, assistant responses, tool calls, and tool results

### 1.3 Database Initialization

**Location**: `backend/app/db/init_db.py`

```python
def init_db() -> None:
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)
```

**When Called**: On FastAPI application startup (`backend/app/main.py`)

```python
@application.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()
```

---

## 2. Database Connection Management

### 2.1 Session Dependency Injection

**Location**: `backend/app/db/base.py`

```python
def get_db():
    """Dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**How It Works**:
1. **FastAPI Dependency**: Used via `Depends(get_db)` in route handlers
2. **Request Lifecycle**: Creates a new session per request
3. **Automatic Cleanup**: Session is closed in `finally` block
4. **Thread Safety**: SQLite configured for multi-threaded access

### 2.2 Connection Pooling

**SQLite Limitations**:
- SQLite doesn't support traditional connection pooling
- Uses file-based database with thread-safe access
- Single database file shared across all connections

**Session Management**:
- Each request gets a new `SessionLocal()` instance
- Sessions are not reused across requests
- Sessions are closed after request completion

**Example Usage in Routes**:
```python
@router.post("/tasks")
def create_task(task_in: TaskCreate, db: Session = Depends(get_db)):
    # db is a fresh session for this request
    task = Task(...)
    db.add(task)
    db.commit()
    # Session automatically closed after function returns
```

### 2.3 WebSocket Connection Handling

**Location**: `backend/app/api/routes/agent.py`

```python
@router.websocket("/agent")
async def agent_websocket(websocket: WebSocket, db: Session = Depends(get_db)):
    # db session is created when WebSocket connects
    agent = TaskAgent(db)
    # Session persists for entire WebSocket connection lifetime
    # ... processing ...
    # Session closed when WebSocket disconnects
```

**Key Points**:
- **Long-Lived Sessions**: WebSocket connections keep the same DB session for the entire connection
- **Agent Initialization**: `TaskAgent` receives the DB session and uses it for all operations
- **Session Scope**: One session per WebSocket connection (not per message)

---

## 3. Caching Implementation

### 3.1 Settings Caching

**Location**: `backend/app/core/settings.py`

```python
@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
```

**How It Works**:
- **LRU Cache**: Python's `functools.lru_cache` decorator
- **Caching Strategy**: Settings object is cached after first call
- **Cache Scope**: Application-wide (process-level)
- **Cache Invalidation**: Never (settings are immutable `@dataclass(frozen=True)`)

**Settings Cached**:
- `project_name`, `version`, `api_prefix`, `environment`
- `deepgram_api_key`, `anthropic_api_key`
- `database_path` (computed property)

### 3.2 No Other Caching

**What's NOT Cached**:
- ❌ Database query results
- ❌ Conversation history
- ❌ Task lists
- ❌ Tool execution results
- ❌ API responses

**Why No Query Caching?**:
- SQLite is fast for small datasets
- Real-time data consistency is important
- No complex queries that would benefit from caching
- Simple architecture without cache invalidation complexity

### 3.3 Potential Caching Opportunities

**If Needed in Future**:
1. **Task Lists**: Cache filtered task lists with TTL
2. **Conversation History**: Cache recent messages (last N messages)
3. **Tool Results**: Cache expensive tool executions
4. **Settings**: Already cached ✅

---

## 4. User Query Processing Flow

### 4.1 WebSocket Endpoint

**Location**: `backend/app/api/routes/agent.py`

**Flow**:
```
1. Client connects to WebSocket: ws://host/api/agent
2. Backend accepts connection
3. Deepgram WebSocket connection established
4. Two concurrent tasks:
   - forward_audio(): Client → Deepgram
   - process_deepgram(): Deepgram → Client + Agent processing
```

### 4.2 Query Processing Pipeline

**Step-by-Step**:

1. **Audio Transcription** (Deepgram FLUX):
   ```
   Client Audio → Deepgram WebSocket → Transcript
   ```

2. **Query Detection**:
   ```python
   if event == "EndOfTurn" and current_transcript:
       query = current_transcript
       # Trigger agent processing
   ```

3. **Agent Initialization**:
   ```python
   agent = TaskAgent(db)  # Uses DB session from WebSocket
   ```

4. **Query Processing**:
   ```python
   async for event in agent.process_query(query):
       # Stream events to client
       await websocket.send_text(json.dumps({
           "type": "agent_event",
           "data": event
       }))
   ```

### 4.3 Agent Query Processing

**Location**: `backend/app/agent/orchestrator.py`

**Method**: `process_query(user_query: str) -> AsyncGenerator`

**Flow**:

```
1. Load Conversation History
   ↓
2. Save User Query to Database
   ↓
3. Build Messages Array (history + new query)
   ↓
4. Stream Claude API Request
   ↓
5. Handle Streaming Events:
   - content_block_start (tool_use)
   - content_block_delta (text/tool input)
   - content_block_stop (tool execution)
   ↓
6. Execute Tools (if any)
   ↓
7. Save Tool Results
   ↓
8. Continue Iteration (max 3 iterations)
   ↓
9. Stream Final Response
   ↓
10. Save Assistant Response
```

**Event Types Yielded**:
- `{"type": "thinking", "content": "..."}`
- `{"type": "tool_use_start", "tool": "..."}`
- `{"type": "tool_use", "tool": "...", "input": {...}}`
- `{"type": "tool_result", "tool": "...", "result": {...}}`
- `{"type": "text", "content": "..."}` (character by character)
- `{"type": "done"}`

### 4.4 Conversation History Loading

**Location**: `backend/app/agent/orchestrator.py` → `_load_conversation_history()`

```python
def _load_conversation_history(self, limit: int = 5) -> list[dict]:
    """Load recent conversation history from database (global, no session filtering)."""
    messages = (
        self.db.query(ConversationMessage)
        .order_by(ConversationMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    # Reverse to get chronological order
    messages.reverse()
    # Format for Claude API...
```

**Key Points**:
- **Global History**: No session filtering (all users share same history)
- **Default Limit**: Last 5 messages
- **Format**: Converts to Claude API message format
- **Tool Calls/Results**: Properly formatted as separate messages

### 4.5 Message Persistence

**Location**: `backend/app/agent/orchestrator.py` → `_save_message()`

**What Gets Saved**:

1. **User Messages**:
   ```python
   ConversationMessage(
       role="user",
       content=user_query,
       tool_calls=None,
       tool_results=None
   )
   ```

2. **Assistant Messages**:
   ```python
   ConversationMessage(
       role="assistant",
       content=assistant_response,
       tool_calls=json.dumps(all_tool_calls),  # JSON string
       tool_results=None
   )
   ```

3. **Tool Result Messages**:
   ```python
   ConversationMessage(
       role="user",  # Note: tool results are user messages
       content="",
       tool_calls=None,
       tool_results=json.dumps(all_tool_results)  # JSON string
   )
   ```

**Database Operations**:
- `db.add(msg)` - Add message to session
- `db.commit()` - Persist to database
- **No Transactions**: Each message is committed immediately

---

## 5. Session Management

### 5.1 Current Implementation: Global History

**Important**: The backend does **NOT** use session-based isolation. All conversation history is **global**.

**Evidence**:
```python
# backend/app/agent/orchestrator.py
def _load_conversation_history(self, limit: int = 5) -> list[dict]:
    """Load recent conversation history from database (global, no session filtering)."""
    messages = (
        self.db.query(ConversationMessage)
        # NO session_id filter!
        .order_by(ConversationMessage.created_at.desc())
        .limit(limit)
        .all()
    )
```

**Impact**:
- All users see the same conversation history
- No user isolation
- No session persistence across reconnects

### 5.2 Session ID Handling (Not Used)

**Code Reference** (from `SESSION_MANAGEMENT.md`):
```python
# This code pattern exists but session_id is not used
def __init__(self, db: Session, session_id: str | None = None):
    self.db = db
    self.session_id = session_id or str(uuid.uuid4())  # Generated but not used
```

**Reality**:
- `session_id` parameter exists in code but is **not used**
- No session filtering in database queries
- No session persistence in frontend

### 5.3 WebSocket Session Handling

**Location**: `backend/app/api/routes/agent.py`

```python
@router.websocket("/agent")
async def agent_websocket(websocket: WebSocket, db: Session = Depends(get_db)):
    # session_id extraction (currently always None)
    # session_id = dict(websocket.query_params).get("session_id")
    
    agent = TaskAgent(db)  # No session_id passed
    # ... processing ...
```

**Current Behavior**:
- Frontend doesn't send `session_id` in WebSocket URL
- Backend doesn't use `session_id` even if provided
- Each WebSocket connection = new agent instance
- Conversation history is global (last 5 messages for everyone)

---

## 6. Tool Execution and Database Interactions

### 6.1 Tool Execution Flow

**Location**: `backend/app/agent/tools.py`

**Tools Available**:
- `create_task`, `create_multiple_tasks`
- `update_task`, `update_multiple_tasks`
- `delete_task`, `delete_multiple_tasks`
- `list_tasks`, `search_tasks`
- `get_task_stats`
- `show_choices`
- `change_ui_view`
- `load_full_history`

**Execution**:
```python
def execute_tool(tool_name: str, tool_input: dict[str, Any], db: Session) -> dict[str, Any]:
    """Execute a tool and return the result."""
    if tool_name == "create_task":
        result = _create_task(db, **tool_input)
    elif tool_name == "list_tasks":
        result = _list_tasks(db, **tool_input)
    # ... etc
```

### 6.2 Database Operations in Tools

**Pattern**:
```python
def _create_task(db: Session, title: str, ...) -> dict[str, Any]:
    task = Task(title=title, ...)
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"success": True, "task": {...}}
```

**Key Points**:
- Tools receive `db: Session` parameter
- Direct SQLAlchemy operations
- Immediate commits (no transactions)
- Results returned as dictionaries

### 6.3 History Search Tool

**Special Tool**: `load_full_history`

**Purpose**: Semantic search through conversation history

**Implementation**:
```python
def _load_full_history(
    db: Session,
    search_terms: list[str] | None = None,
    tools: list[str] | None = None,
    limit: int = 2,
) -> dict[str, Any]:
    # Searches conversation_messages table
    # Filters by keywords and tool names
    # Returns relevant conversation cycles
```

**Use Cases**:
- "restore deleted task" → search for delete operations
- "what options did you show?" → search for show_choices
- "undo last update" → search for update operations

---

## 7. Connection Lifecycle

### 7.1 Application Startup

```
1. FastAPI app created
2. Database engine initialized (SQLite)
3. Database tables created (if not exist)
4. Settings loaded and cached
5. API routes registered
6. CORS middleware configured
```

### 7.2 Request Lifecycle (HTTP)

```
1. Request arrives
2. FastAPI creates new DB session (get_db dependency)
3. Route handler executes
4. Database operations performed
5. Response returned
6. DB session closed (finally block)
```

### 7.3 WebSocket Connection Lifecycle

```
1. WebSocket connection established
2. DB session created (get_db dependency)
3. Deepgram WebSocket connected
4. Agent initialized with DB session
5. Audio forwarding loop (concurrent)
6. Deepgram processing loop (concurrent)
7. Query processing (on EndOfTurn events)
8. WebSocket disconnects
9. DB session closed
10. Deepgram connection closed
```

### 7.4 Query Processing Lifecycle

```
1. User query received (from Deepgram transcript)
2. Conversation history loaded (last 5 messages)
3. User query saved to database
4. Claude API streaming request
5. Tool calls executed (if any)
6. Tool results saved to database
7. Assistant response streamed
8. Assistant response saved to database
9. "done" event sent
```

---

## 8. Performance Considerations

### 8.1 Database Performance

**SQLite Characteristics**:
- ✅ Fast for small to medium datasets
- ✅ No network latency (local file)
- ✅ Simple setup (no server required)
- ❌ Limited concurrency (file-based)
- ❌ No connection pooling (not needed for SQLite)

**Optimizations**:
- Thread-safe connection (`check_same_thread=False`)
- Query logging disabled (`echo=False`)
- Indexed primary keys
- Efficient queries (no N+1 problems observed)

### 8.2 Caching Impact

**Current State**: Minimal caching
- Only settings cached (immutable, rarely accessed)
- No query result caching
- No conversation history caching

**Performance Impact**:
- Database queries executed on every request
- Conversation history loaded from DB on every query
- No significant performance issues (small dataset)

### 8.3 WebSocket Performance

**Concurrent Processing**:
- Audio forwarding and Deepgram processing run concurrently
- Non-blocking I/O (async/await)
- Timeout protection (30 seconds for agent processing)

**Bottlenecks**:
- Claude API latency (external dependency)
- Deepgram transcription latency (external dependency)
- Database writes (immediate commits)

---

## 9. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                     │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              API Routes (router.py)                    │   │
│  │  - /api/agent (WebSocket)                            │   │
│  │  - /api/tasks (HTTP)                                  │   │
│  │  - /api/conversation (HTTP)                           │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                   │
│                           ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Database Session (get_db dependency)          │   │
│  │  - New session per request/WebSocket                  │   │
│  │  - Auto-closed after request                          │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                   │
│                           ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              SQLite Database (shram.db)                │   │
│  │  - tasks table                                         │   │
│  │  - conversation_messages table                         │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              TaskAgent (orchestrator.py)               │   │
│  │  - process_query() - streaming                        │   │
│  │  - _load_conversation_history()                       │   │
│  │  - _save_message()                                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                   │
│                           ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Claude API (Anthropic)                        │   │
│  │  - Streaming responses                                │   │
│  │  - Tool calling                                       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Deepgram API (FLUX)                            │   │
│  │  - Real-time transcription                            │   │
│  │  - WebSocket connection                                │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Caching Layer (Minimal)                   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         @lru_cache (settings.py)                      │   │
│  │  - get_settings() - cached after first call           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 10. Key Findings and Recommendations

### 10.1 Current State

✅ **What Works Well**:
- Simple, straightforward architecture
- Fast for small datasets (SQLite)
- Proper session management (one per request)
- Streaming responses for real-time UX
- Global conversation history (if intentional)

⚠️ **Potential Issues**:
- **No Supabase**: User mentioned Supabase, but backend uses SQLite
- **Global History**: All users share same conversation history
- **No Session Isolation**: No user/session-based filtering
- **Minimal Caching**: No query result caching
- **Immediate Commits**: No transaction batching

### 10.2 Recommendations

**If Migrating to Supabase**:
1. Replace SQLite engine with PostgreSQL connection string
2. Update `backend/app/db/base.py` to use Supabase connection
3. Add connection pooling (Supabase supports it)
4. Consider Supabase real-time subscriptions for live updates

**If Adding Session Isolation**:
1. Add `session_id` column to `conversation_messages` table
2. Filter queries by `session_id`
3. Generate and persist `session_id` in frontend (localStorage)
4. Pass `session_id` in WebSocket connection

**If Adding Caching**:
1. Cache recent conversation history (last N messages)
2. Cache task lists with TTL (5-10 seconds)
3. Use Redis for distributed caching (if scaling)
4. Implement cache invalidation on writes

**If Optimizing Database**:
1. Add indexes on frequently queried columns
2. Batch commits for multiple operations
3. Use transactions for atomic operations
4. Consider read replicas if scaling

---

## 11. Summary

### Database
- **Type**: SQLite (file-based)
- **ORM**: SQLAlchemy
- **Connection**: Thread-safe, one session per request
- **Pooling**: Not applicable (SQLite)

### Caching
- **Settings**: Cached via `@lru_cache`
- **Queries**: Not cached
- **History**: Not cached

### Query Processing
- **Entry Point**: WebSocket `/api/agent`
- **Flow**: Deepgram → Transcript → Agent → Claude → Tools → Response
- **Streaming**: Character-by-character text streaming
- **History**: Last 5 messages loaded automatically

### Session Management
- **Current**: Global history (no isolation)
- **Sessions**: Not used (despite code references)
- **Persistence**: Database only (no frontend persistence)

### Connection Management
- **HTTP**: New session per request (auto-closed)
- **WebSocket**: One session per connection (closed on disconnect)
- **Thread Safety**: SQLite configured for multi-threaded access

---

**Document Generated**: Comprehensive analysis of backend architecture
**Last Updated**: Based on current codebase state
**Note**: No Supabase connections found - backend uses SQLite



