# UI Control Feature

## Overview

The agent can now control the frontend UI by switching views and changing dates based on voice commands.

## Implementation Details

### Backend Changes

1. **New Tool: `change_ui_view`** (`backend/app/agent/tools.py`)
   - Parameters:
     - `view_mode`: "daily" | "weekly" | "monthly" | "list"
     - `target_date`: Optional ISO date string (YYYY-MM-DD)
   - Returns a special `ui_command` object in the result

2. **Enhanced System Prompt** (`backend/app/agent/orchestrator.py`)
   - Includes current date and time in UTC
   - Provides examples of how to use the UI control tool
   - Helps agent understand relative dates like "tomorrow", "next week", "December"

### Frontend Changes

1. **AgentVoiceButton Component** (`frontend/components/AgentVoiceButton.tsx`)
   - New prop: `onUICommand(command)`
   - Detects `ui_command` in tool results
   - Forwards command to parent component

2. **Main Page** (`frontend/app/page.tsx`)
   - New handler: `handleUICommand(command)`
   - Updates `viewMode` state
   - Updates `selectedDate` state

## How It Works

```
1. User says: "Show me tasks for December"
   
2. FLUX detects EndOfTurn → sends transcript to agent

3. Agent processes:
   - Sees current date (e.g., November 16, 2025)
   - Understands "December" means December 2025
   - Calls change_ui_view tool:
     {
       "view_mode": "monthly",
       "target_date": "2025-12-01"
     }

4. Tool returns:
   {
     "success": true,
     "ui_command": {
       "type": "change_view",
       "view_mode": "monthly",
       "target_date": "2025-12-01"
     },
     "message": "Switched to monthly view for 2025-12-01"
   }

5. Frontend receives tool_result event:
   - Extracts ui_command
   - Calls onUICommand handler
   - Updates viewMode to "monthly"
   - Updates selectedDate to December 1, 2025

6. UI automatically re-renders with new view
```

## Example Commands

| Voice Command | Agent Action | UI Result |
|--------------|--------------|-----------|
| "Show me December tasks" | `change_ui_view(monthly, 2025-12-01)` | Monthly view for Dec 2025 |
| "What's next week?" | `change_ui_view(weekly, 2025-11-23)` | Weekly view starting next Monday |
| "Show today's tasks" | `change_ui_view(daily, 2025-11-16)` | Daily view for today |
| "Switch to list view" | `change_ui_view(list)` | List view (date unchanged) |
| "Show me January" | `change_ui_view(monthly, 2025-01-01)` | Monthly view for Jan 2025 |

## Date Interpretation

The agent has access to the current date and can interpret relative dates:

- **"today"** → Current date
- **"tomorrow"** → Current date + 1 day
- **"next week"** → Monday of next week
- **"December"** → First day of December (current or next year)
- **"next month"** → First day of next month
- **"Monday"** → Next occurring Monday

## Testing

1. Start the backend and frontend servers
2. Click the voice button
3. Try these commands:
   - "Show me tasks for December"
   - "What's happening next week?"
   - "Switch to daily view"
   - "Show me today's schedule"

The UI should automatically switch views and dates as you speak!

## Technical Notes

- The agent receives the current UTC time in its system prompt
- Date calculations happen in the agent using Python's datetime
- The frontend receives ISO date strings and converts them to JavaScript Date objects
- The view change happens instantly when the tool result is received
- Multiple view changes can be chained (e.g., "Show December, then next week")

## Future Enhancements

- Add more granular time navigation (specific hours for daily view)
- Support date ranges ("show me tasks from Monday to Friday")
- Add visual feedback when view changes (animation/highlight)
- Support "go back to previous view" command

