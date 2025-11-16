# Voice Agent Improvements

## 1. Concise Response System

### System Prompt Updates
The agent now distinguishes between two types of requests:

**"Show" Commands** → UI Change + Brief Confirmation
- "Show me December tasks" → Switch to monthly view + respond "Showing December"
- "Display urgent tasks" → Switch to filtered list + respond "Showing urgent tasks"
- Response: 2-3 words maximum

**"Tell/List/Read" Commands** → Provide Actual Details
- "Tell me December tasks" → List each task with title, priority, deadline
- "Read my urgent tasks" → Provide bullet list of urgent tasks
- "What are my tasks?" → Detailed task listing

### Response Guidelines
- **Task created/updated/deleted**: "Done" or "Created" (1-2 words)
- **View changed**: "Showing [period]" (2-3 words)
- **Listing tasks**: Concise bullet list with key details
- **Errors**: Brief error message

### Implementation
```python
# System prompt now includes:
"1. Understand their intent clearly - distinguish between 'show' (UI change) vs 'tell/list/read' (provide details)"
"6. ALWAYS keep final responses very brief (1-2 sentences max) unless explicitly asked to list/read tasks"
```

## 2. User Interrupt Capability

### How It Works
Users can interrupt the agent mid-response by simply starting to speak.

### Implementation Details

1. **Frontend Detection**:
   - FLUX continuously transcribes user speech
   - When user speaks during agent response, transcript length increases
   - If `canInterrupt` flag is true and transcript length > 3 characters, trigger interrupt

2. **Interrupt Flow**:
   ```
   Agent speaking → User starts talking → FLUX detects speech
   → Frontend clears agent response → User's new query processed
   ```

3. **Code**:
   ```typescript
   // In AgentVoiceButton.tsx
   if (canInterrupt && fluxData.transcript.length > 3) {
     console.log('User interruption detected, clearing agent response');
     setAgentResponse('');
     setToolActivity('');
     setIsProcessing(false);
     setCanInterrupt(false);
   }
   ```

### When Interruption Is Allowed
- ✅ During text response streaming (canInterrupt = true)
- ❌ During "thinking" phase (canInterrupt = false)
- ❌ During tool execution (canInterrupt = false)

## 3. Latency Optimizations

### Changes Made

1. **Immediate Feedback**:
   - Agent yields "thinking" event immediately on start
   - Frontend shows "Processing..." instantly

2. **Reduced Token Limit**:
   - Changed from 4096 to 1024 tokens
   - Faster generation for concise responses

3. **Reduced Conversation History**:
   - Changed from 20 to 10 messages
   - Faster context loading

4. **Added Timing Logs**:
   - Track EndOfTurn detection time
   - Monitor agent processing speed

### Expected Latency Breakdown
```
User stops speaking → EndOfTurn (0.7-1.5s, FLUX threshold)
                   → Agent start signal (<0.1s)
                   → Thinking indicator shown (<0.1s)
                   → Claude API response (1-3s for tool calls)
                   → Text streaming starts (immediate)
                   → Total: ~2-5s
```

## 4. UI Improvements

### Completed Task Styling
- ✅ Strikethrough text on completed tasks (all views)
- ✅ Reduced opacity for completed tasks
- ✅ Green checkmark icon in list view

### Task Reload Optimization
- Added 300ms delay before reloading tasks after agent updates
- Prevents UI from going blank during updates

## 5. List View Filters (Agent Control)

The agent can now control list view filters and sorting.

### New Tool Parameters
```python
change_ui_view(
    view_mode="list",
    sort_by="priority",        # deadline, priority, created
    sort_order="desc",          # asc, desc
    filter_status="urgent",     # all, todo, in_progress, completed, cancelled
    filter_priority="high"      # all, urgent, high, medium, low
)
```

### Voice Commands
- "Show tasks sorted by priority" → List view, sorted by priority descending
- "Show urgent tasks only" → List view, filtered by urgent priority
- "Show completed tasks" → List view, filtered by completed status
- "Show high priority tasks sorted by deadline" → List view with both filters

## 6. Future: Text-to-Speech (TTS)

### Recommended Approach: Web Speech API

**Pros**:
- Built into browsers (no API key needed)
- Zero latency (local synthesis)
- Free
- Easy to implement

**Implementation**:
```typescript
const utterance = new SpeechSynthesisUtterance(agentResponse);
utterance.rate = 1.1; // Slightly faster for efficiency
utterance.pitch = 1.0;
utterance.voice = voices.find(v => v.lang === 'en-US');
window.speechSynthesis.speak(utterance);

// Stop on interrupt
window.speechSynthesis.cancel();
```

### Alternative: Deepgram Aura TTS (Premium)

**Pros**:
- Higher quality voices
- More natural prosody
- Consistent across browsers

**Cons**:
- Requires API calls ($)
- Added latency
- Need to handle audio playback

**Would need**:
- Separate HTTP endpoint or WebSocket for TTS
- Audio streaming to browser
- Web Audio API for playback

### Recommendation
Start with **Web Speech API** because:
1. Instant playback (no network latency)
2. Free
3. Simple interrupt mechanism (cancel synthesis)
4. Works well for short, concise responses

Upgrade to Deepgram Aura later if voice quality becomes critical.

## Testing the New Features

### Test Concise Responses
1. Say: "Create a task for tomorrow"
   - Expected: Agent responds "Created" or "Done"
2. Say: "Show me December tasks"
   - Expected: UI switches to December, agent says "Showing December"
3. Say: "Tell me my urgent tasks"
   - Expected: Agent lists each urgent task with details

### Test Interruption
1. Say: "Tell me all my tasks" (long response)
2. Start speaking while agent is responding
3. Expected: Agent response clears, your new input is processed

### Test Filters
1. Say: "Show tasks sorted by priority"
   - Expected: UI switches to list view, sorted by priority
2. Say: "Show only urgent tasks"
   - Expected: List view with urgent filter applied

## Performance Tips

1. **Keep responses brief** → Faster generation, better UX
2. **Use UI changes over listings** → More efficient
3. **Clear conversation history periodically** → Faster context loading
4. **Monitor backend logs** → Identify latency bottlenecks

## Known Limitations

1. **Interrupt doesn't stop backend processing** → Backend continues until done, but frontend stops displaying
2. **No TTS yet** → Responses are text-only (add Web Speech API for audio)
3. **FLUX EOT threshold** → 0.7s minimum silence required, can't reduce further without false triggers

