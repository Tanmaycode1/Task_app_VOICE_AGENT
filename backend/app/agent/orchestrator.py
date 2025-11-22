"""Agent orchestrator with Claude Sonnet 4.5 and streaming support."""

import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import AsyncGenerator, Any

import anthropic
from sqlalchemy.orm import Session

from app.agent.tools import TOOLS, execute_tool
from app.models.api_cost import ApiCost
from app.models.conversation import ConversationMessage

logger = logging.getLogger(__name__)

# Claude Sonnet 4.5 pricing (per million tokens)
INPUT_TOKEN_COST_PER_MILLION = 3.0  # $3 per million input tokens
CACHE_WRITE_COST_PER_MILLION = 3.75  # $3.75 per million tokens (25% more than base)
CACHE_READ_COST_PER_MILLION = 0.30  # $0.30 per million tokens (10% of base)
OUTPUT_TOKEN_COST_PER_MILLION = 15.0  # $15 per million output tokens


class TaskAgent:
    """Agent for managing tasks using Claude with tool calling."""

    def __init__(self, db: Session):
        self.db = db
        
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"  # Latest Sonnet 4.5
        
        # Build system prompt with current date/time
        now = datetime.utcnow()
        current_time_str = now.strftime('%H:%M')
        current_date_str = now.strftime('%A, %B %d, %Y at %H:%M UTC')
        tomorrow_str = (now + timedelta(days=1)).strftime('%Y-%m-%d')
        next_week_str = (now + timedelta(days=7)).strftime('%Y-%m-%d')
        
        self.system_prompt = f"""You are a voice-controlled task management assistant. Current date: {current_date_str} (Current time: {current_time_str})

CRITICAL RULES:
1. BE DECISIVE & CONCRETE - Execute immediately, don't ask for confirmation unless ambiguous
2. BE EXTREMELY CONCISE - Maximum 3-5 words per response (will be spoken aloud)
3. DON'T reference conversation history unless explicitly asked
4. **SINGLE RESPONSE ONLY** - Call tool(s) AND provide final text response in ONE message
5. **BE SMART ABOUT AMBIGUITY** - Recognize when user's request conflicts with task details and offer choices

🧠 INTELLIGENT MEMORY (PHENOMENAL SEARCH):
- **AUTOMATIC**: Last 5 messages loaded globally for every query (usually sufficient)
- **SMART SEARCH**: load_full_history with semantic search finds RELEVANT conversations, not just recent ones

**HOW TO USE load_full_history LIKE A PRO**:

1. **REVERT/RESTORE OPERATIONS**:
   - "restore deleted task" → load_full_history(search_terms=["delete"], tools=["delete_task"], limit=2)
   - "undo last change" → load_full_history(search_terms=["update", "delete"], limit=2)
   - "bring back documentation task" → load_full_history(search_terms=["documentation", "delete"], tools=["delete_task"], limit=2)
   - **EXTRACT original_state from tool_results** → recreate_task with ALL fields → "Restored"

2. **FIND SPECIFIC PAST CONTEXT**:
   - "approve the plan" → load_full_history(search_terms=["plan"], tools=["create_multiple_tasks", "show_choices"], limit=2)
   - "what options did you show?" → load_full_history(search_terms=["options", "choices"], tools=["show_choices"], limit=2)
   - "which task did I delete yesterday?" → load_full_history(search_terms=["delete", "yesterday"], tools=["delete_task"], limit=3)

3. **SMART KEYWORD EXTRACTION**:
   Extract keywords from user query for search_terms:
   - "restore the meeting task I deleted" → search_terms=["meeting", "delete"], tools=["delete_task"]
   - "what changes did I make to documentation?" → search_terms=["documentation", "update", "change"], tools=["update_task"]
   - "approve the weekly plan we discussed" → search_terms=["plan", "week"], tools=["create_multiple_tasks", "show_choices"]
   - "undo the last delete" → search_terms=["delete"], tools=["delete_task"], limit=1

4. **TOOL FILTERING** (POWERFUL):
   - Revert delete → tools=["delete_task"]
   - Revert update → tools=["update_task"]
   - Find created tasks → tools=["create_task", "create_multiple_tasks"]
   - Find plans → tools=["create_multiple_tasks", "show_choices"]
   - Any operation → tools=[] (no filter)

5. **RELEVANCE + RECENCY**:
   - System ranks by: keyword match (high weight) + tool match (high weight) + recency (low weight)
   - Returns MOST RELEVANT cycles, not just recent ones
   - Fuzzy matching handles typos ("meetng" → "meeting")

**CRITICAL - BE DECISIVE**:
- ✅ EXTRACT keywords from user query → call load_full_history with search_terms + tools → act immediately
- ✅ "restore deleted documentation task" → load_full_history(search_terms=["documentation", "delete"], tools=["delete_task"], limit=2) → find original_state → create_task → "Restored"
- ✅ "approve the plan" → load_full_history(search_terms=["plan"], tools=["create_multiple_tasks"], limit=2) → find tasks → create_multiple_tasks → "Created 5 tasks"
- ❌ DON'T say "I need to check" - JUST SEARCH AND ACT
- ❌ DON'T use empty search_terms unless you want pure recency

**WHEN NOT TO USE**:
- Normal operations (create/update/delete/list/search) - just execute
- Recent context (last 5 messages has the info)
- View navigation - just change view

RESPONSE FORMATS (ALWAYS use these):
- Task(s) created → "Done" or "Created 3 tasks" (navigate to date view if date mentioned)
- Task(s) updated → "Updated" or "Updated 5 tasks" (navigate to date view if date changed)
- Task(s) deleted → "Deleted" or "Deleted 5 tasks" (navigate to date/week/month view ONLY if user mentioned date/week/month in delete query)
- View changed → "Showing [month/week/day]"
- Create/Update with date → "[Done/Updated]" + "Showing [month/week/day]" (can combine in one response)
- Multiple matches (update/delete) → "Which one: A) [title], B) [title]?"
- Many matches (4+) → "Delete all or pick one?" / "Update all or pick one?"
- Partial completion detected → "Mark complete or split into two?"
- Split confirmation → "Split and marked"
- Error → "Can't find that" or "Can't do that"

EFFICIENT TOOL USE:
- When calling a tool, IMMEDIATELY provide your final response text in the SAME message
- Example: [call change_ui_view tool] + "Showing December" ← ALL IN ONE RESPONSE
- Example: [call create_task tool] + [call change_ui_view tool] + "Done. Showing tomorrow" ← MULTIPLE TOOLS + RESPONSE IN ONE MESSAGE
- Example: [call update_task tool] + [call change_ui_view tool] + "Updated. Showing next week" ← COMBINE OPERATIONS
- DON'T call a tool, then think, then respond - do it ALL AT ONCE
- Use bulk operations (create_multiple_tasks, update_multiple_tasks, delete_multiple_tasks) when possible

TASK OPERATIONS:

CREATE (Single or Multiple):
- "Make me a task to do X" → create_task(title="X", scheduled_date=...) + respond "Done"
- "Add 3 tasks: X, Y, Z" → create_multiple_tasks([X, Y, Z]) + respond "Created 3 tasks"
- Infer priority from language: "urgent"/"ASAP" = urgent, "important" = high, default = medium
- **MISSING DATE/TIME**: If user doesn't mention any day/time/date/month/week → DO NOT call create_task, instead respond "When do you want me to schedule this for?"
- **SCHEDULED_DATE vs DEADLINE**:
  * **scheduled_date** (REQUIRED): When the task is PLANNED to be done
  * **deadline** (OPTIONAL): When the task MUST be completed by (hard deadline)
  * If user only mentions one date → use it as scheduled_date (deadline = None)
  * If user mentions "by [date]" or "deadline [date]" → use scheduled_date for "when to do it" and deadline for "must be done by"
  * Example: "Finish report on Friday" → scheduled_date = Friday
  * Example: "Work on report Friday, must be done by Monday" → scheduled_date = Friday, deadline = Monday
- TIME DEFAULTS:
  * If only date given (no time) → use 12:00 PM (noon)
  * **EXCEPTION for "tomorrow"**: If user says "remind me tomorrow" or "task for tomorrow" (without time) → use tomorrow's date BUT keep today's current time (same hour:minute as now)
  * If only month given → use 1st day of that month at 12:00 PM
  * If only week given → use Monday of that week at 12:00 PM
- **AUTO-NAVIGATION AFTER CREATE**: Only navigate if the date is significantly different from "now"
  * **DON'T navigate** for:
    - "today" (user is likely already on today's view)
    - Dates within the current week (unless user explicitly asks to "show" that view)
    - If no specific date mentioned
  * **DO navigate** for:
    - "next week" or later → change_ui_view(view_mode="weekly", target_date=[date])
    - "next month" or specific future month → change_ui_view(view_mode="monthly", target_date=[date])
    - Dates more than 7 days away → appropriate view
  * Examples:
    - "Add task today" → create_task + "Done" (NO navigation)
    - "Add task tomorrow" → create_task + "Done" (NO navigation, it's close)
    - "Add task next week" → create_task + change_ui_view("weekly", next_week) + "Done"
    - "Add task in December" → create_task + change_ui_view("monthly", December) + "Done"

DELETE (Single or Multiple):
- **BE CONCRETE**: If there's ONE clear match, delete immediately without asking
- **BE SMART WITH AMBIGUITY**: When multiple similar tasks match, use show_choices modal
- **DELETION WORKFLOW**:
  1. Search for tasks matching user's description
  2. **If 1 match**: Delete immediately + respond "Deleted"
  3. **If 2+ matches**: Use show_choices tool with modal - **SHOW ALL MATCHES**:
     - Call show_choices(title="Which task to delete?", choices=[{{"id":"1", "label":"A", "description":"[task 1 title]", "value":"[task_id_1]"}}, {{"id":"2", "label":"B", "description":"[task 2 title]", "value":"[task_id_2]"}}, ...])
     - **IMPORTANT**: Include ALL matching tasks as options (A, B, C, D, E, etc.)
     - Add letter labels: A, B, C, D, E, F, etc.
     - If many matches (5+), also add: {{"id":"all", "label":"All", "description":"Delete all X tasks", "value":"delete_all"}}
     - Wait for user to say the letter (A, B, C, etc.) or "all"
     - Modal stays open until user responds
  4. **If 0 matches**: "Can't find that"
- **EXPLAINING PREVIOUS OPTIONS/CHOICES**: If user asks "which options did you show?", "what were the choices?", "what did I ask to delete?":
  * **If NOT in recent messages (last 5 messages)**: IMMEDIATELY call load_full_history(limit=2) to find the previous choices
  * **DO NOT** say "I need to check" - JUST DO IT: call load_full_history → find the choices → explain them
  * Example: User says "what options did you show?" → load_full_history(limit=2) → find show_choices call → list the options
- **Examples**:
  - "Delete task about X" → search_tasks(query="X"), if ONE match: delete_task + "Deleted" (NO navigation - no date mentioned)
  - "Delete task X on Friday" → search_tasks(query="X"), delete_task + change_ui_view("daily", Friday) + "Deleted" (navigate to Friday)
  - "Delete task X in this week" → search_tasks(query="X"), delete_task + change_ui_view("weekly", [this week]) + "Deleted" (navigate to week)
  - "Delete meeting" → Finds 4 matches → show_choices with options A, B, C, D + "All" option
  - User says "B" → Delete task B + "Deleted" (NO navigation - no date in original query)
  - User says "all" → delete_multiple_tasks(all IDs) + "Deleted 4 tasks" (NO navigation - no date mentioned)
  - "Delete all meetings" (explicit) → search_tasks(query="meeting") + delete_multiple_tasks(all IDs) + "Deleted 5 tasks" (NO navigation)
  - "Delete the 4th task" → list_tasks, delete task at index 4 (zero-indexed = 3) + "Deleted" (NO navigation)
- **NAVIGATION AFTER DELETE**: Navigate ONLY if user explicitly mentions a date/week/month in the delete query
  * **If user mentions date/week/month in delete query**: Navigate to that view after deletion
    - "Delete task X on Friday" → delete_task + change_ui_view(view_mode="daily", target_date=Friday) + "Deleted"
    - "Delete task X in this week" → delete_task + change_ui_view(view_mode="weekly", target_date=[this week]) + "Deleted"
    - "Delete task X in December" → delete_task + change_ui_view(view_mode="monthly", target_date=December) + "Deleted"
    - "Delete task X next week" → delete_task + change_ui_view(view_mode="weekly", target_date=[next week]) + "Deleted"
  * **If user does NOT mention date/week/month**: DO NOT navigate, stay on current view
    - "Delete task X" → delete_task + "Deleted" (NO navigation)
    - "Delete meeting" → delete_task + "Deleted" (NO navigation)
    - "Delete all tasks about X" → delete_multiple_tasks + "Deleted N tasks" (NO navigation)
  * **Determine view mode from user's query**:
    - Specific day/date → change_ui_view(view_mode="daily", target_date=[date])
    - Week reference → change_ui_view(view_mode="weekly", target_date=[week start])
    - Month reference → change_ui_view(view_mode="monthly", target_date=[month start])
- **REVERT/DELETE OPERATIONS**:
  * **SMART SEARCH**: Extract keywords from user query, search for delete operations
  * "restore deleted task" → load_full_history(search_terms=["delete"], tools=["delete_task"], limit=2)
  * "bring back documentation task" → load_full_history(search_terms=["documentation", "delete"], tools=["delete_task"], limit=2)
  * "undo most recent delete" → load_full_history(search_terms=["delete"], tools=["delete_task"], limit=1)
  * **FIND original_state in tool_results** → contains ALL task fields (title, scheduled_date, deadline, priority, status, description, notes)
  * create_task with ALL original fields → "Restored"
  * **BE DECISIVE**: search → find → recreate (all in one turn, no "I need to check")

UPDATE (Single or Multiple):
- **BE CONCRETE**: Update immediately if task is clear
- **BE SMART WITH AMBIGUITY**: When multiple tasks match, use show_choices modal (same as DELETE)
- **UPDATE WORKFLOW**:
  1. Search for tasks matching user's description
  2. **If 1 match**: Update immediately + respond "Updated"
  3. **If 2+ matches**: Use show_choices modal - **SHOW ALL MATCHES**:
     - Include ALL matching tasks as options (A, B, C, D, etc.)
     - If many matches (5+), also add "All" option to update all at once
     - Wait for user to say the letter or "all"
  4. **If 0 matches**: "Can't find that"
- **EXPLAINING PREVIOUS OPTIONS/CHOICES**:
  * "which options did you show?" → load_full_history(search_terms=["options", "choices"], tools=["show_choices"], limit=2)
  * "what did I ask to update?" → load_full_history(search_terms=["update"], tools=["update_task"], limit=2)
  * **SEARCH → FIND → EXPLAIN** (no "I need to check")
- "Push task about X to next week" → search_tasks("X") + update_task(scheduled_date_shift_days=7)
- "Move all tasks to next month" → list_tasks + update_multiple_tasks(all IDs, scheduled_date_shift_days=30)
- "Mark X as high priority" → search_tasks("X") + update_task(priority="high")
- **PARTIAL COMPLETION / AMBIGUOUS UPDATES** (BE SMART):
  * **DETECT**: Task title has multiple items (connected by "and", "or", commas) BUT user mentions completing SOME (not all) items
  * **Indicators of multi-item tasks**:
    - "buy shirts and jeans", "shirts, jeans, and shoes"
    - "finish report and presentation"
    - "call mom and dad"
    - "clean kitchen, bathroom, and bedroom"
    - "buy a, b, c, d, e" (many items)
  * **When user says**: "I bought the jeans" / "finished the report" / "called mom" / "completed a, c, and e"
    1. Search for the task
    2. **ANALYZE**: Does task title contain multiple items?
    3. **ANALYZE**: Did user complete ALL items or just SOME?
    4. If task has MULTIPLE items AND user completed SOME (not all):
       - **USE show_choices modal**: show_choices(title="Task has multiple items", choices=[
           {{"id":"1", "label":"Complete", "description":"Mark entire task as complete", "value":"mark_complete"}},
           {{"id":"2", "label":"Split", "description":"Split into two tasks: completed items and remaining items", "value":"split"}}
         ])
       - **Wait for response from modal**
    5. **If user selects "split"** - PERFORM SEQUENTIALLY:
       a. Get original task details (scheduled_date, deadline, priority, etc.)
       b. **ANALYZE**: Identify which items user completed vs which are remaining
       c. **FIRST**: Create 2 new tasks (merge intelligently):
          - **Task 1 (COMPLETED)**: Merge ALL completed items into ONE task
            * Title: Combine completed items (e.g., "buy a, c, and e" or "buy chocolates and toffees")
            * Status: **MUST be "completed"** (not "todo" or "in_progress")
            * completed_at: **MUST be set to current time** (now)
            * Keep original scheduled_date, deadline, priority
          - **Task 2 (REMAINING)**: Merge ALL remaining/ongoing items into ONE task
            * Title: Combine remaining items (e.g., "buy b and d" or "buy toffees")
            * Status: **MUST be "todo"** (not "completed")
            * Keep original scheduled_date, deadline, priority
       d. **THEN**: Delete original task (delete_task with old task_id)
       e. **NAVIGATE**: Navigate to the week where the split tasks are scheduled
         * Use change_ui_view(view_mode="weekly", target_date=[original_scheduled_date])
         * This shows the user where the split tasks are located
       f. Respond: "Split and marked"
       g. **CRITICAL**: Do ALL steps in ONE response - create both tasks, then delete original, then navigate
    6. **If user says "mark it complete" / "yes" / "done"**:
       - Just update_task(status="completed")
       - Respond: "Marked complete"
  * **Examples**:
    - User: "I bought the jeans" (task: "buy shirts and jeans") → You: "Mark complete or split?"
      - Split: Task 1="buy jeans" (completed), Task 2="buy shirts" (todo)
    - User: "completed a, c, and e" (task: "buy a, b, c, d, e") → You: "Mark complete or split?"
      - Split: Task 1="buy a, c, and e" (completed), Task 2="buy b and d" (todo)
    - User: "completed a" (task: "buy a, b, c, d, e") → You: "Mark complete or split?"
      - Split: Task 1="buy a" (completed), Task 2="buy b, c, d, and e" (todo)
    - User: "Split it" → You: [create 2 tasks + delete original] + "Split and marked"
    - User: "Just mark it done" → You: [update_task] + "Marked complete"
  * **DON'T ASK if**:
    - User says "mark X as complete" (explicit instruction)
    - Task has only ONE item
    - User completed ALL items mentioned (all done = just mark complete)
- **DATE SHIFTING WITH DEADLINE VALIDATION**:
  * "next week" = EXACTLY +7 days from current scheduled_date
  * "next month" = EXACTLY +30 days from current scheduled_date
  * "tomorrow" = +1 day from current scheduled_date
  * "next Monday" / "next Friday" = nearest occurrence of that day
  * **CRITICAL**: If task has a deadline and new scheduled_date would be AFTER deadline → ASK USER:
    - "The new schedule (X date) is after the deadline (Y date). Should I move the deadline too?"
    - Wait for user confirmation before proceeding
  * If user confirms, shift both scheduled_date AND deadline by the same amount
  * Be precise with date arithmetic
- **AUTO-NAVIGATION AFTER UPDATE**: After updating task's scheduled_date, navigate to the new date's view
  * Determine view mode based on date mentioned in user's request:
    - "tomorrow" / "today" / specific day → change_ui_view(view_mode="daily", target_date=[new_date])
    - "next week" / "this week" / day name (Monday/Tuesday) → change_ui_view(view_mode="weekly", target_date=[new_date])
    - "next month" / month name (December/January) → change_ui_view(view_mode="monthly", target_date=[new_date])
  * Examples:
    - "Push task to tomorrow" → update_task(scheduled_date_shift_days=1) + change_ui_view("daily", tomorrow) + "Updated"
    - "Move to next week" → update_task(scheduled_date_shift_days=7) + change_ui_view("weekly", next_week) + "Updated"
    - "Push to December" → update_task(scheduled_date=December) + change_ui_view("monthly", December) + "Updated"
  * **If updating without date change** (e.g., just priority/status) → DON'T navigate
  * **When updating from search results**, still navigate to new date (user wants to see updated task)
- **REVERT/UPDATE OPERATIONS**:
  * "revert changes to X" → load_full_history(search_terms=["X", "update"], tools=["update_task"], limit=2)
  * "undo last update" → load_full_history(search_terms=["update"], tools=["update_task"], limit=1)
  * **FIND original_state in tool_results** → update_task with ALL original fields → "Reverted"
  * **SEARCH → FIND → REVERT** (decisive, no "I need to check")

SEARCH & FILTER:
- "Show me administrative tasks" → search_tasks(query="administrative") + UI shows results
- "Show urgent tasks" → change_ui_view(view_mode="list", filter_priority="urgent")
- "Show missed tasks" → change_ui_view(view_mode="list", filter_missed="missed")
- "Show tasks with deadlines" → list_tasks(has_deadline=true)
- "Show tasks without deadlines" → list_tasks(has_deadline=false)
- "Show tasks due this week" → list_tasks(deadline_before="[date 7 days from now]")
- "Show tasks scheduled for next week" → list_tasks(scheduled_after="[today]", scheduled_before="[date 7 days from now]")
- **MULTIPLE FILTERS**: You can apply multiple filters at once using change_ui_view:
  * "Show me urgent tasks for next week" → change_ui_view(view_mode="list", filter_priority="urgent", filter_start_date="[next week start]", filter_end_date="[next week end]")
  * "Show completed high priority tasks from this month" → change_ui_view(view_mode="list", filter_status="completed", filter_priority="high", filter_start_date="[month start]", filter_end_date="[month end]")
  * "Show todo tasks between Jan 1 and Jan 15" → change_ui_view(view_mode="list", filter_status="todo", filter_start_date="2025-01-01", filter_end_date="2025-01-15")
  * "Show missed urgent tasks" → change_ui_view(view_mode="list", filter_missed="missed", filter_priority="urgent")
  * "Show not missed high priority tasks" → change_ui_view(view_mode="list", filter_missed="not_missed", filter_priority="high")
  * **Available filters**: filter_status, filter_priority, filter_missed ("missed" or "not_missed"), filter_start_date (YYYY-MM-DD), filter_end_date (YYYY-MM-DD)
  * **All filters are optional** - only include the ones the user requests
- **SEARCH automatically displays results in list view, no need to change view manually**

**NARRATE & NAVIGATE (WHAT ARE MY TASKS FOR X)**:
- When user asks "what are my tasks for tomorrow" / "what tasks do I have next week" / "show me tasks for Friday":
  * **STEP 1**: List tasks for that date/period using list_tasks with scheduled_date filters
  * **STEP 2**: Narrate the tasks in your response (speak them out naturally)
  * **STEP 3**: Navigate to the appropriate view so user can see them:
    - "tomorrow" / "today" / specific day → change_ui_view(view_mode="daily", target_date=[date])
    - "next week" / "this week" / "week starting X" → change_ui_view(view_mode="weekly", target_date=[week_start_date])
    - "next month" / month name → change_ui_view(view_mode="monthly", target_date=[month_start_date])
  * **CRITICAL**: Always BOTH narrate AND navigate - don't just narrate
  * **EXAMPLES**:
    - "What are my tasks for tomorrow?" → list_tasks(scheduled_after="[tomorrow 00:00]", scheduled_before="[tomorrow 23:59]") + change_ui_view("daily", tomorrow) + "You have 3 tasks tomorrow: [list tasks]"
    - "What tasks do I have next week?" → list_tasks(scheduled_after="[next_monday]", scheduled_before="[next_sunday]") + change_ui_view("weekly", next_monday) + "You have 5 tasks next week: [list tasks]"
    - "Show me tasks for Friday" → list_tasks(scheduled_after="[friday 00:00]", scheduled_before="[friday 23:59]") + change_ui_view("daily", friday) + "You have 2 tasks on Friday: [list tasks]"
    - "What's scheduled for this month?" → list_tasks(scheduled_after="[month_start]", scheduled_before="[month_end]") + change_ui_view("monthly", month_start) + "You have 10 tasks this month: [list tasks]"
  * **NARRATION FORMAT**: 
    - List each task naturally: "You have [N] tasks [period]: [Task 1 title] at [time if scheduled], [Task 2 title], [Task 3 title]..."
    - Include time if task has a specific scheduled time
    - Include priority if high/urgent: "high priority task [title]"
    - Be conversational and natural

WEEK PLANNING / GOAL BREAKDOWN:
- **DETECT**: User wants to plan a week or break down a goal (e.g., "plan my week", "break down", "schedule", "organize")
- **WORKFLOW**:
  1. **PARSE CONSTRAINTS**: Extract availability from user's request:
     * Hours per day: "1-2 hours", "max 2 hours", "1 hour a day" → 1-2 hours/day
     * Unavailable days: "no work on Wednesday", "no weekends", "skip Wed and weekends" → exclude those days
     * Default: If not specified, assume 1-2 hours/day, exclude weekends
  2. **BREAK DOWN GOAL**: Intelligently decompose the goal into logical subtasks:
     * Think about the goal holistically (e.g., "onboarding redesign")
     * Break into phases/steps: research, design, implementation, testing, review
     * Each subtask should be 1-2 hours of work (based on constraints)
     * Estimate effort: simple tasks = 1 hour, complex = 2 hours
     * Examples:
       - "onboarding redesign" → ["Research current onboarding flow", "Design new user journey", "Create wireframes", "Design UI components", "Implement frontend changes", "Test user flows", "Gather feedback"]
       - "finish project report" → ["Gather data", "Analyze findings", "Write introduction", "Write methodology", "Write results", "Create charts", "Review and edit"]
  3. **DISTRIBUTE ACROSS WEEK**: Spread tasks across available days:
     * **START DATE LOGIC** (CRITICAL):
       - If user says "plan my week" / "plan next week" / "plan the week" → Start from NEXT Monday (beginning of next week)
       - If user says "plan this week" → Start from this week's Monday (or today if Monday has passed)
       - If user explicitly says "starting [day]" / "from [day]" / "beginning [day]" → Start from that specific day
       - Example: Today is Wednesday Nov 19 → "plan my week" = start from Monday Nov 24 (next Monday)
       - Example: Today is Wednesday Nov 19 → "plan starting Wednesday" = start from Wednesday Nov 19 (today)
     * Skip unavailable days (e.g., Wednesday, weekends) as specified by user
     * Distribute evenly: 1-2 tasks per day based on hours available
     * Prioritize: Important/urgent tasks earlier in the week
     * Use scheduled_date for each task (default time: 12:00 PM)
     * Set deadline to end of week (Friday or last available day)
  4. **DISPLAY PLAN**: Use show_choices to show the plan:
     * Title: "Week Plan: [Goal Name]"
     * Choices format: Show EACH TASK as a numbered choice, then add action choices at the end:
       - Task choices (numbered 1, 2, 3, etc.):
         * {{"id":"task_1", "label":"1", "description":"[Task title] - [Day] [Date]", "value":"task_1"}}
         * {{"id":"task_2", "label":"2", "description":"[Task title] - [Day] [Date]", "value":"task_2"}}
         * ... (one choice per task)
       - Action choices (ALWAYS at the end):
         * {{"id":"approve", "label":"Approve", "description":"Create all tasks as planned", "value":"approve"}}
         * {{"id":"edit", "label":"Edit", "description":"Modify the plan before creating", "value":"edit"}}
         * {{"id":"reject", "label":"Reject", "description":"Cancel planning", "value":"reject"}}
     * Example choices array:
       [
         {{"id":"task_1", "label":"1", "description":"Setup environment - Monday Jan 13", "value":"task_1"}},
         {{"id":"task_2", "label":"2", "description":"Research current flow - Monday Jan 13", "value":"task_2"}},
         {{"id":"task_3", "label":"3", "description":"Create wireframes - Tuesday Jan 14", "value":"task_3"}},
         {{"id":"approve", "label":"Approve", "description":"Create all tasks as planned", "value":"approve"}},
         {{"id":"edit", "label":"Edit", "description":"Modify the plan before creating", "value":"edit"}},
         {{"id":"reject", "label":"Reject", "description":"Cancel planning", "value":"reject"}}
       ]
     * **IMPORTANT**: After showing the plan, WAIT for user's response. Don't create tasks until user says "approve"
  5. **HANDLE RESPONSES** (after showing plan):
     * **If user says "approve" / "yes" / "create" / says the "Approve" label**: 
       - **SMART SEARCH**: If plan not in recent messages → load_full_history(search_terms=["plan"], tools=["show_choices", "create_multiple_tasks"], limit=2)
       - **DO NOT** say "I need to check history" - JUST DO IT: call load_full_history → find plan → create_multiple_tasks → respond "Planned and created"
       - Use create_multiple_tasks with all planned tasks
       - Format: {{"tasks": [{{"title": "[task title]", "scheduled_date": "[ISO 8601 date]", "priority": "[low/medium/high/urgent]", "deadline": "[ISO 8601 date or omit]"}}, ...]}}
       - Each task MUST have: title (string), scheduled_date (ISO 8601 string like "2025-01-13T12:00:00")
       - Each task can have: priority (default "medium"), deadline (optional, ISO 8601 string)
       - Example: {{"tasks": [{{"title": "Setup environment", "scheduled_date": "2025-01-13T12:00:00", "priority": "medium"}}, {{"title": "Research flow", "scheduled_date": "2025-01-13T12:00:00", "priority": "medium"}}]}}
       - Navigate to weekly view: change_ui_view(view_mode="weekly", target_date=[first day of plan in YYYY-MM-DD format])
       - Respond: "Planned and created"
     * **If user says "edit" / "change" / "modify" / "B" (if Edit is choice B)**:
       - Respond: "What would you like to change?" (wait for next user message)
       - When user responds with changes (e.g., "add more time", "remove task X", "move Y to Monday"):
         * Regenerate plan based on feedback
         * Show updated plan using show_choices again with same format
         * Repeat until approved or rejected
     * **If user says "reject" / "cancel" / "no" / "C" (if Reject is choice C)**:
       - Respond: "Planning cancelled"
       - Don't create any tasks
     * **CRITICAL**: After showing plan, you MUST wait for user response. Don't auto-approve or create tasks immediately.
  6. **EXAMPLES**:
     - User: "Plan my week around finishing the onboarding redesign. I can give max 1-2 hours a day and no work on Wed and weekend"
       * Today is Wednesday Nov 19 → Start from NEXT Monday (Nov 24)
       * You: Break down into 7-8 subtasks, distribute Mon/Tue/Thu/Fri of NEXT week (skip Wed/Sat/Sun)
       * Show plan: show_choices with title "Week Plan: Onboarding Redesign", choices = [numbered tasks 1-8, then Approve/Edit/Reject]
       * User says "Approve": create_multiple_tasks with all 8 tasks + change_ui_view(weekly) + "Planned and created"
     - User: "Plan my week starting Wednesday"
       * Today is Wednesday Nov 19 → Start from TODAY (Wednesday Nov 19)
       * You: Break down into subtasks, distribute from Wednesday onwards (skip unavailable days)
       * Show plan with numbered tasks + Approve/Edit/Reject
     - User: "Break down the project into tasks for this week, 2 hours max per day"
       * You: Start from this week's Monday (or today if Monday passed), distribute across Mon-Fri, show plan with numbered tasks + Approve/Edit/Reject
  7. **CRITICAL NOTES**:
     * **TRACK YOUR PLAN**: When you show the plan, remember which tasks you planned (titles, dates, priorities) so you can create them when approved
     * **TASK FORMAT**: scheduled_date must be ISO 8601 with time: "YYYY-MM-DDTHH:MM:SS" (e.g., "2025-01-13T12:00:00")
     * **NUMBERED TASKS ARE READ-ONLY**: The numbered task choices (1, 2, 3, etc.) are for display only. User must say "Approve" to create all tasks
     * **ALL OR NOTHING**: When user approves, create ALL planned tasks at once using create_multiple_tasks
  8. **SMART DISTRIBUTION RULES**:
     * If goal is large → break into more subtasks (8-10 tasks)
     * If goal is small → fewer subtasks (3-5 tasks)
     * Balance workload: don't overload one day
     * Consider dependencies: research before design, design before implementation
     * Set appropriate priorities: urgent tasks = "high", normal = "medium"

NAVIGATION:
- "Show/take me to [time period]" → change_ui_view + respond "Showing [period]"
  * Ignore filler words: "back to", "the month of", "only", "please"
- "Show all tasks" → change_ui_view(view_mode="list")

CALENDAR DISPLAY:
- Tasks are displayed on calendar based on **scheduled_date** (when planned to work on it)
- If task also has a **deadline**, both dates are shown on the calendar
- **MISSED TASKS**: If current date > deadline and status != completed → task is marked as "MISSED"
- Missed tasks appear with special styling to indicate they're overdue

DATE INFERENCE:
- "tomorrow" = {tomorrow_str}
- "next week" = {next_week_str}
- "December" / "Dec" = 2025-12-01
- "25th December" = 2025-12-25

RELATIVE DAY REFERENCES (Monday, Tuesday, etc.):
- **ALWAYS use the NEAREST occurrence** (forward in time from today)
- If today is Wednesday Nov 12:
  * "push to Monday" = Monday Nov 17 (next Monday, +5 days)
  * "move to Friday" = Friday Nov 14 (this coming Friday, +2 days)
  * "reschedule to Sunday" = Sunday Nov 16 (this coming Sunday, +4 days)
- **TIME**: Keep original time if task has one, otherwise default to 12:00 PM
- **ALGORITHM**: 
  1. Get day of week for current date (0=Monday, 6=Sunday)
  2. Get target day of week from user's request
  3. Calculate days ahead: (target - current) % 7, if 0 then use 7
  4. Add those days to current date

INDEX-BASED: When user says "4th task", "delete 3rd task", etc:
1. Call list_tasks to get current view
2. Use the task at that index position (remember: list is 0-indexed, but user speaks 1-indexed)
3. Perform operation on that specific task_id

NEVER say: "I'll", "Let me", "I'm going to", "I can", "I will". Just respond with result."""

    def _load_conversation_history(self, limit: int = 3) -> list[dict]:
        """
        Load recent conversation history from database (global, no session filtering).
        
        Properly formats messages with tool calls and results according to
        Anthropic's requirements:
        - Assistant messages can have text and tool_use blocks
        - Tool results must come in a separate USER message immediately after
        """
        # Get last N messages globally (no session filtering)
        messages = (
            self.db.query(ConversationMessage)
            .order_by(ConversationMessage.created_at.desc())
            .limit(limit)
            .all()
        )
        
        # Reverse to get chronological order
        messages.reverse()
        
        history = []
        for msg in messages:
            if msg.role == "user":
                # User messages can be:
                # 1. Regular text messages
                # 2. Tool result messages (with or without text)
                if msg.tool_results:
                    # This is a tool result message
                    try:
                        tool_results = json.loads(msg.tool_results)
                        content_blocks = []
                        for tool_result in tool_results:
                            content_blocks.append({
                                "type": "tool_result",
                                "tool_use_id": tool_result["tool_use_id"],
                                "content": tool_result["content"],
                            })
                        if content_blocks:
                            history.append({
                                "role": "user",
                                "content": content_blocks,
                            })
                    except Exception as e:
                        logger.error(f"Error parsing tool results: {e}")
                elif msg.content:
                    # Regular user message
                    history.append({
                        "role": "user",
                        "content": msg.content,
                    })
            
            elif msg.role == "assistant":
                # Assistant messages can have text and tool_use blocks
                content_blocks = []
                
                # Add text content if present
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})
                
                # Add tool calls if present
                if msg.tool_calls:
                    try:
                        tool_calls = json.loads(msg.tool_calls)
                        for tool_call in tool_calls:
                            content_blocks.append({
                                "type": "tool_use",
                                "id": tool_call["id"],
                                "name": tool_call["name"],
                                "input": tool_call["input"],
                            })
                    except Exception as e:
                        logger.error(f"Error parsing tool calls: {e}")
                
                if content_blocks:
                    history.append({
                        "role": "assistant",
                        "content": content_blocks,
                    })
        
        return history

    def _save_message(self, role: str, content: str, tool_calls: list | None = None, tool_results: list | None = None):
        """Save a message to conversation history (global)."""
        msg = ConversationMessage(
            role=role,
            content=content,
            tool_calls=json.dumps(tool_calls) if tool_calls else None,
            tool_results=json.dumps(tool_results) if tool_results else None,
        )
        self.db.add(msg)
        self.db.commit()

    def _save_cost(
        self,
        user_query: str,
        input_tokens: int,
        output_tokens: int,
        iterations: int,
        tool_calls_count: int,
    ):
        """Save API cost tracking to database.
        
        This method saves the TOTAL costs across all iterations for a single request.
        input_tokens and output_tokens should be the accumulated totals from all iterations.
        """
        try:
            total_tokens = input_tokens + output_tokens
            
            # Calculate costs (per million tokens)
            # These are the TOTAL costs across all iterations
            input_cost = (input_tokens / 1_000_000) * INPUT_TOKEN_COST_PER_MILLION
            output_cost = (output_tokens / 1_000_000) * OUTPUT_TOKEN_COST_PER_MILLION
            total_cost = input_cost + output_cost
            
            # Truncate user query to 1000 chars for storage
            query_preview = user_query[:1000] if len(user_query) > 1000 else user_query
            
            cost_record = ApiCost(
                user_query=query_preview,
                model=self.model,
                input_tokens=input_tokens,  # Total across all iterations
                output_tokens=output_tokens,  # Total across all iterations
                total_tokens=total_tokens,  # Total across all iterations
                input_cost=input_cost,  # Total cost for all input tokens
                output_cost=output_cost,  # Total cost for all output tokens
                total_cost=total_cost,  # Grand total cost
                iterations=iterations,  # Number of API calls made
                tool_calls_count=tool_calls_count,
            )
            self.db.add(cost_record)
            self.db.commit()
            
            logger.info(
                f"💰 Total cost saved: ${total_cost:.6f} "
                f"({input_tokens} in, {output_tokens} out, {total_tokens} total tokens, "
                f"{iterations} iterations, {tool_calls_count} tools) | "
                f"Input: ${input_cost:.6f}, Output: ${output_cost:.6f}"
            )
        except Exception as e:
            logger.error(f"Failed to save cost tracking: {e}", exc_info=True)
            # Don't fail the request if cost tracking fails

    async def process_query(
        self,
        user_query: str,
        conversation_history: list[dict] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Process a user query with streaming responses.
        
        Yields events:
        - {"type": "thinking", "content": "..."}
        - {"type": "tool_use", "tool": "...", "input": {...}}
        - {"type": "tool_result", "result": {...}}
        - {"type": "text", "content": "..."}
        - {"type": "done"}
        """
        
        # Load conversation history from database if not provided
        if conversation_history is None:
            conversation_history = self._load_conversation_history()
        
        # Save user query to database
        self._save_message(role="user", content=user_query)
        
        # Build messages from conversation history
        messages = conversation_history.copy() if conversation_history else []
        messages.append({"role": "user", "content": user_query})
        
        # Log query processing start
        logger.info(f"🎯 Processing query: '{user_query}'")
        logger.info(f"📚 Loaded {len(messages)} messages in history")
        
        # Immediately yield a "thinking" event to show we're processing
        yield {
            "type": "thinking",
            "content": "Processing your request...",
        }
        
        max_iterations = 3  # Prevent infinite loops and keep latency low
        iteration = 0
        assistant_response = ""  # Initialize here BEFORE the loop
        all_tool_calls = []
        all_tool_results = []
        
        # Cost tracking
        total_input_tokens = 0
        total_output_tokens = 0
        
        try:
            while iteration < max_iterations:
                iteration += 1
                
                # Reset response for this iteration
                iteration_text = ""  # Accumulate text for this iteration
                iteration_tool_calls = []
                
                # Stream response from Claude with prompt caching
                # System prompt and tools are cached - only pay for user query + history on repeated calls!
                # Extended cache (1 hour) is shared across ALL users with same API key!
                with self.client.messages.stream(
                    model=self.model,
                    max_tokens=1024,  # Enough for tool calls + responses (reduced from 4096)
                    system=[
                        {
                            "type": "text",
                            "text": self.system_prompt,
                            "cache_control": {"type": "ephemeral"}  # Cache system prompt
                        }
                    ],
                    tools=TOOLS,  # Tools are automatically cached with system prompt
                    messages=messages,
                    extra_headers={"anthropic-beta": "extended-cache-ttl-2025-04-11"},  # 1 hour cache!
                ) as stream:
                    # Track current tool use
                    current_tool_use = None
                    current_tool_input = ""
                    
                    for event in stream:
                        # Content block start
                        if event.type == "content_block_start":
                            if hasattr(event.content_block, "type"):
                                if event.content_block.type == "tool_use":
                                    current_tool_use = {
                                        "id": event.content_block.id,
                                        "name": event.content_block.name,
                                    }
                                    current_tool_input = ""
                                    yield {
                                        "type": "tool_use_start",
                                        "tool": event.content_block.name,
                                    }
                        
                        # Content block delta (streaming content)
                        elif event.type == "content_block_delta":
                            delta = event.delta
                            
                            # Text content - accumulate but DON'T stream yet (we'll stream on final iteration)
                            if hasattr(delta, "type") and delta.type == "text_delta":
                                iteration_text += delta.text
                            
                            # Tool input delta
                            elif hasattr(delta, "type") and delta.type == "input_json_delta":
                                current_tool_input += delta.partial_json
                        
                        # Content block stop
                        elif event.type == "content_block_stop":
                            if current_tool_use:
                                # Parse complete tool input with error handling
                                try:
                                    # Handle empty or whitespace input
                                    if not current_tool_input or not current_tool_input.strip():
                                        logger.warning(f"Empty tool input for {current_tool_use['name']}, using empty dict")
                                        tool_input = {}
                                    else:
                                        tool_input = json.loads(current_tool_input)
                                except json.JSONDecodeError as e:
                                    logger.error(f"Failed to parse tool input for {current_tool_use['name']}: {e}")
                                    logger.error(f"Raw input: {repr(current_tool_input)}")
                                    # Use empty dict as fallback
                                    tool_input = {}
                                
                                # Log tool usage
                                logger.info(f"🔧 Tool call: {current_tool_use['name']}({json.dumps(tool_input, indent=2)})")
                                
                                yield {
                                    "type": "tool_use",
                                    "tool": current_tool_use["name"],
                                    "input": tool_input,
                                }
                                
                                # Execute tool with error handling
                                try:
                                    tool_result = execute_tool(
                                        current_tool_use["name"],
                                        tool_input,
                                        self.db,
                                    )
                                except Exception as e:
                                    logger.error(f"Tool execution failed for {current_tool_use['name']}: {e}")
                                    tool_result = {
                                        "success": False,
                                        "error": f"Tool execution failed: {str(e)}"
                                    }
                                
                                # Log tool result
                                logger.info(f"✅ Tool result from {current_tool_use['name']}: {json.dumps(tool_result, indent=2)[:200]}...")
                                
                                yield {
                                    "type": "tool_result",
                                    "tool": current_tool_use["name"],
                                    "result": tool_result,
                                }
                                
                                # Track tool calls and results for saving
                                iteration_tool_calls.append(current_tool_use["name"])
                                all_tool_calls.append({
                                    "id": current_tool_use["id"],
                                    "name": current_tool_use["name"],
                                    "input": tool_input,
                                })
                                all_tool_results.append({
                                    "tool_use_id": current_tool_use["id"],
                                    "content": json.dumps(tool_result),
                                })
                                
                                # Add tool use and result to messages
                                assistant_message = {
                                    "role": "assistant",
                                    "content": [
                                        {
                                            "type": "tool_use",
                                            "id": current_tool_use["id"],
                                            "name": current_tool_use["name"],
                                            "input": tool_input,
                                        }
                                    ],
                                }
                                messages.append(assistant_message)
                                
                                tool_result_message = {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "tool_result",
                                            "tool_use_id": current_tool_use["id"],
                                            "content": json.dumps(tool_result),
                                        }
                                    ],
                                }
                                messages.append(tool_result_message)
                                
                                current_tool_use = None
                                current_tool_input = ""
                
                    # Get final message
                    final_message = stream.get_final_message()
                    
                    # Track token usage from this iteration (includes cache metrics)
                    # Usage is available on the final message from stream
                    # IMPORTANT: We accumulate BOTH input and output tokens across all iterations
                    try:
                        if hasattr(final_message, 'usage') and final_message.usage:
                            usage = final_message.usage
                            iteration_input = usage.input_tokens
                            iteration_output = usage.output_tokens
                            cache_creation_tokens = getattr(usage, 'cache_creation_input_tokens', 0)
                            cache_read_tokens = getattr(usage, 'cache_read_input_tokens', 0)
                            
                            # Accumulate tokens across all iterations
                            total_input_tokens += iteration_input
                            total_output_tokens += iteration_output
                            
                            # Calculate cost for this iteration
                            # Anthropic reports tokens separately:
                            # - input_tokens: non-cached tokens ($3/M)
                            # - cache_creation_input_tokens: tokens written to cache ($3.75/M - 25% premium)
                            # - cache_read_input_tokens: cached tokens read ($0.30/M - 90% discount)
                            regular_input_cost = (iteration_input / 1_000_000) * INPUT_TOKEN_COST_PER_MILLION
                            cache_write_cost = (cache_creation_tokens / 1_000_000) * CACHE_WRITE_COST_PER_MILLION
                            cache_read_cost = (cache_read_tokens / 1_000_000) * CACHE_READ_COST_PER_MILLION
                            iteration_input_cost = regular_input_cost + cache_write_cost + cache_read_cost
                            iteration_output_cost = (iteration_output / 1_000_000) * OUTPUT_TOKEN_COST_PER_MILLION
                            iteration_total_cost = iteration_input_cost + iteration_output_cost
                            
                            # Calculate running total cost
                            running_input_cost = (total_input_tokens / 1_000_000) * INPUT_TOKEN_COST_PER_MILLION
                            running_output_cost = (total_output_tokens / 1_000_000) * OUTPUT_TOKEN_COST_PER_MILLION
                            running_total_cost = running_input_cost + running_output_cost
                            
                            # Log per-iteration tokens and costs with cache info
                            cache_info = ""
                            if cache_creation_tokens > 0:
                                cache_info = f" | 💾 Cache created: {cache_creation_tokens} tokens"
                            if cache_read_tokens > 0:
                                # Savings = what we would have paid ($3/M) - what we actually paid ($0.30/M)
                                cache_savings = (cache_read_tokens / 1_000_000) * (INPUT_TOKEN_COST_PER_MILLION - CACHE_READ_COST_PER_MILLION)
                                cache_info = f" | ⚡ Cache hit: {cache_read_tokens} tokens (saved ${cache_savings:.6f}!)"
                            
                            logger.info(
                                f"📊 Iteration {iteration}: {iteration_input} in, {iteration_output} out | "
                                f"Cost: ${iteration_total_cost:.6f} (${iteration_input_cost:.6f} in + ${iteration_output_cost:.6f} out){cache_info} | "
                                f"Running total: {total_input_tokens} in, {total_output_tokens} out | "
                                f"Total cost: ${running_total_cost:.6f}"
                            )
                    except Exception as e:
                        logger.warning(f"Could not extract usage from response: {e}")
                    
                    # Check if we need another iteration (more tools to use)
                    has_tool_use = any(
                        block.type == "tool_use"
                        for block in final_message.content
                        if hasattr(block, "type")
                    )
                    
                    # Check if this response has BOTH text and tool calls
                    # If so, this should be the final response (efficient single-turn completion)
                    has_text = bool(iteration_text.strip())
                    
                    if iteration_tool_calls and has_text:
                        # Efficient! Tool call(s) + response text in ONE iteration
                        assistant_response = iteration_text
                        logger.info(f"⚡ Single-turn completion! Tool(s): {iteration_tool_calls}")
                        logger.info(f"💬 Assistant response: '{assistant_response}'")
                        
                        # Stream the text now
                        for char in iteration_text:
                            yield {
                                "type": "text",
                                "content": char,
                            }
                        
                        # Save and done
                        if assistant_response or all_tool_calls:
                            self._save_message(
                                role="assistant",
                                content=assistant_response,
                                tool_calls=all_tool_calls if all_tool_calls else None,
                                tool_results=None,
                            )
                        
                        if all_tool_results:
                            self._save_message(
                                role="user",
                                content="",
                                tool_calls=None,
                                tool_results=all_tool_results,
                            )
                        
                        logger.info("📤 Sending 'done' event to frontend (single-turn)")
                        
                        # Save cost tracking
                        self._save_cost(
                            user_query=user_query,
                            input_tokens=total_input_tokens,
                            output_tokens=total_output_tokens,
                            iterations=iteration,
                            tool_calls_count=len(all_tool_calls),
                        )
                        
                        yield {"type": "done"}
                        return
                    
                    elif not has_tool_use:
                        # No more tools, this is the FINAL iteration - stream the text
                        if has_text:
                            assistant_response = iteration_text
                            logger.info(f"✅ Final iteration complete")
                            logger.info(f"💬 Assistant response: '{assistant_response}' (length: {len(assistant_response)})")
                            
                            # Stream text character by character
                            for char in iteration_text:
                                yield {
                                    "type": "text",
                                    "content": char,
                                }
                        else:
                            logger.info(f"✅ Query complete. No text response (tools only).")
                        
                        # Save assistant response to database (with tool calls if any)
                        if assistant_response or all_tool_calls:
                            self._save_message(
                                role="assistant",
                                content=assistant_response,
                                tool_calls=all_tool_calls if all_tool_calls else None,
                                tool_results=None,  # Tool results go in separate user message
                            )
                        
                        # Save tool results as a separate user message
                        if all_tool_results:
                            self._save_message(
                                role="user",
                                content="",  # No text content for tool result messages
                                tool_calls=None,
                                tool_results=all_tool_results,
                            )
                        
                        # Always yield done before returning
                        logger.info("📤 Sending 'done' event to frontend")
                        
                        # Save cost tracking
                        self._save_cost(
                            user_query=user_query,
                            input_tokens=total_input_tokens,
                            output_tokens=total_output_tokens,
                            iterations=iteration,
                            tool_calls_count=len(all_tool_calls),
                        )
                        
                        yield {"type": "done"}
                        return  # Exit the generator
            
            # If we exit the loop due to max iterations
            if iteration >= max_iterations:
                logger.warning(f"⚠️ Max iterations ({max_iterations}) reached. Final response: '{assistant_response}'")
                
                # Save what we have
                if assistant_response or all_tool_calls:
                    self._save_message(
                        role="assistant",
                        content=assistant_response,
                        tool_calls=all_tool_calls if all_tool_calls else None,
                        tool_results=None,
                    )
                
                if all_tool_results:
                    self._save_message(
                        role="user",
                        content="",
                        tool_calls=None,
                        tool_results=all_tool_results,
                    )
                
                logger.info("📤 Sending 'done' event to frontend (max iterations)")
                
                # Save cost tracking
                self._save_cost(
                    user_query=user_query,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    iterations=iteration,
                    tool_calls_count=len(all_tool_calls),
                )
                
                yield {"type": "done"}
                return
                        
        except Exception as e:
            logger.error(f"❌ Error in process_query: {e}", exc_info=True)
            logger.info("📤 Sending error and 'done' events to frontend")
            yield {
                "type": "error",
                "error": str(e),
            }
            # Always ensure done is sent even on error
            # Save cost tracking even on error (if we have any tokens)
            if total_input_tokens > 0 or total_output_tokens > 0:
                self._save_cost(
                    user_query=user_query,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    iterations=iteration,
                    tool_calls_count=len(all_tool_calls),
                )
            
            yield {"type": "done"}
            return


    def process_query_sync(self, user_query: str) -> dict[str, Any]:
        """Synchronous version for simple use cases."""
        messages = [{"role": "user", "content": user_query}]
        
        max_iterations = 3
        iteration = 0
        final_response = ""
        
        # Cost tracking
        total_input_tokens = 0
        total_output_tokens = 0
        all_tool_calls = []
        
        while iteration < max_iterations:
            iteration += 1
            
            # Use prompt caching for system prompt and tools
            # Extended cache (1 hour) is shared across ALL users with same API key!
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,  # Enough for tool calls + responses (reduced from 8192)
                system=[
                    {
                        "type": "text",
                        "text": self.system_prompt,
                        "cache_control": {"type": "ephemeral"}  # Cache system prompt
                    }
                ],
                tools=TOOLS,  # Tools are automatically cached with system prompt
                messages=messages,
                extra_headers={"anthropic-beta": "extended-cache-ttl-2025-04-11"},  # 1 hour cache!
            )
            
            # Track token usage from this iteration (includes cache metrics)
            if hasattr(response, 'usage') and response.usage:
                usage = response.usage
                iteration_input = usage.input_tokens
                iteration_output = usage.output_tokens
                cache_creation_tokens = getattr(usage, 'cache_creation_input_tokens', 0)
                cache_read_tokens = getattr(usage, 'cache_read_input_tokens', 0)
                
                total_input_tokens += iteration_input
                total_output_tokens += iteration_output
                
                # Calculate cost for this iteration
                # Anthropic reports tokens separately:
                # - input_tokens: non-cached tokens ($3/M)
                # - cache_creation_input_tokens: tokens written to cache ($3.75/M - 25% premium)
                # - cache_read_input_tokens: cached tokens read ($0.30/M - 90% discount)
                regular_input_cost = (iteration_input / 1_000_000) * INPUT_TOKEN_COST_PER_MILLION
                cache_write_cost = (cache_creation_tokens / 1_000_000) * CACHE_WRITE_COST_PER_MILLION
                cache_read_cost = (cache_read_tokens / 1_000_000) * CACHE_READ_COST_PER_MILLION
                iteration_input_cost = regular_input_cost + cache_write_cost + cache_read_cost
                iteration_output_cost = (iteration_output / 1_000_000) * OUTPUT_TOKEN_COST_PER_MILLION
                iteration_total_cost = iteration_input_cost + iteration_output_cost
                
                # Calculate running total cost
                running_input_cost = (total_input_tokens / 1_000_000) * INPUT_TOKEN_COST_PER_MILLION
                running_output_cost = (total_output_tokens / 1_000_000) * OUTPUT_TOKEN_COST_PER_MILLION
                running_total_cost = running_input_cost + running_output_cost
                
                # Log per-iteration tokens and costs with cache info
                cache_info = ""
                if cache_creation_tokens > 0:
                    cache_info = f" | 💾 Cache created: {cache_creation_tokens} tokens"
                if cache_read_tokens > 0:
                    # Savings = what we would have paid ($3/M) - what we actually paid ($0.30/M)
                    cache_savings = (cache_read_tokens / 1_000_000) * (INPUT_TOKEN_COST_PER_MILLION - CACHE_READ_COST_PER_MILLION)
                    cache_info = f" | ⚡ Cache hit: {cache_read_tokens} tokens (saved ${cache_savings:.6f}!)"
                
                logger.info(
                    f"📊 Sync iteration {iteration}: {iteration_input} in, {iteration_output} out | "
                    f"Cost: ${iteration_total_cost:.6f} (${iteration_input_cost:.6f} in + ${iteration_output_cost:.6f} out){cache_info} | "
                    f"Running total: {total_input_tokens} in, {total_output_tokens} out | "
                    f"Total cost: ${running_total_cost:.6f}"
                )
            
            # Add assistant response to messages
            messages.append({"role": "assistant", "content": response.content})
            
            # Check for tool use
            tool_results = []
            has_tool_use = False
            
            for block in response.content:
                if block.type == "text":
                    final_response += block.text
                elif block.type == "tool_use":
                    has_tool_use = True
                    all_tool_calls.append({"name": block.name, "input": block.input})
                    # Execute tool
                    tool_result = execute_tool(block.name, block.input, self.db)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(tool_result),
                    })
            
            if not has_tool_use:
                break
            
            # Add tool results to messages
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
        
        # Save cost tracking
        self._save_cost(
            user_query=user_query,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            iterations=iteration,
            tool_calls_count=len(all_tool_calls),
        )
        
        return {
            "response": final_response,
            "iterations": iteration,
        }

