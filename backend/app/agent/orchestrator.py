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
from app.models.conversation import ConversationMessage

logger = logging.getLogger(__name__)


class TaskAgent:
    """Agent for managing tasks using Claude with tool calling."""

    def __init__(self, db: Session, session_id: str | None = None):
        self.db = db
        self.session_id = session_id or str(uuid.uuid4())
        
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

RESPONSE FORMATS (ALWAYS use these):
- Task(s) created → "Done" or "Created 3 tasks" (navigate to date view if date mentioned)
- Task(s) updated → "Updated" or "Updated 5 tasks" (navigate to date view if date changed)
- Task(s) deleted → "Deleted" or "Deleted 5 tasks"
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
- **Examples**:
  - "Delete task about X" → search_tasks(query="X"), if ONE match: delete_task immediately
  - "Delete meeting" → Finds 4 matches → show_choices with options A, B, C, D + "All" option
  - User says "B" → Delete task B + "Deleted"
  - User says "all" → delete_multiple_tasks(all IDs) + "Deleted 4 tasks"
  - "Delete all meetings" (explicit) → search_tasks(query="meeting") + delete_multiple_tasks(all IDs) + "Deleted 5 tasks"
  - "Delete the 4th task" → list_tasks, delete task at index 4 (zero-indexed = 3)
- **CRITICAL: After deleting tasks, DO NOT change the view/screen - stay on the current view**
- **DO NOT call change_ui_view after delete_task or delete_multiple_tasks**

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

SEARCH & FILTER:
- "Show me administrative tasks" → search_tasks(query="administrative") + UI shows results
- "Show urgent tasks" → list_tasks(priority="urgent")
- "Show missed tasks" → list_tasks(is_missed=true)
- "Show tasks with deadlines" → list_tasks(has_deadline=true)
- "Show tasks without deadlines" → list_tasks(has_deadline=false)
- "Show tasks due this week" → list_tasks(deadline_before="[date 7 days from now]")
- "Show tasks scheduled for next week" → list_tasks(scheduled_after="[today]", scheduled_before="[date 7 days from now]")
- **SEARCH automatically displays results in list view, no need to change view manually**

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

    def _load_conversation_history(self, limit: int = 2) -> list[dict]:
        """
        Load recent conversation history from database.
        
        Properly formats messages with tool calls and results according to
        Anthropic's requirements:
        - Assistant messages can have text and tool_use blocks
        - Tool results must come in a separate USER message immediately after
        """
        messages = (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.session_id == self.session_id)
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
        """Save a message to conversation history."""
        msg = ConversationMessage(
            session_id=self.session_id,
            role=role,
            content=content,
            tool_calls=json.dumps(tool_calls) if tool_calls else None,
            tool_results=json.dumps(tool_results) if tool_results else None,
        )
        self.db.add(msg)
        self.db.commit()

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
        
        # Debug: log message format
        logger.info(f"Processing query with {len(messages)} messages in history")
        
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
        
        try:
            while iteration < max_iterations:
                iteration += 1
                
                # Reset response for this iteration
                iteration_text = ""  # Accumulate text for this iteration
                iteration_tool_calls = []
                
                # Stream response from Claude
                with self.client.messages.stream(
                    model=self.model,
                    max_tokens=4096,  # Doubled for Sonnet 4.5 - supports longer responses and complex operations
                    system=self.system_prompt,
                    tools=TOOLS,
                    messages=messages,
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
                        logger.info(f"⚡ Single-turn completion! Tool(s): {iteration_tool_calls} + Text: '{assistant_response}'")
                        
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
                        yield {"type": "done"}
                        return
                    
                    elif not has_tool_use:
                        # No more tools, this is the FINAL iteration - stream the text
                        if has_text:
                            assistant_response = iteration_text
                            logger.info(f"✅ Final iteration. Streaming text: '{assistant_response}' (length: {len(assistant_response)})")
                            
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
            yield {"type": "done"}
            return


    def process_query_sync(self, user_query: str) -> dict[str, Any]:
        """Synchronous version for simple use cases."""
        messages = [{"role": "user", "content": user_query}]
        
        max_iterations = 3
        iteration = 0
        final_response = ""
        
        while iteration < max_iterations:
            iteration += 1
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,  # Doubled for Sonnet 4.5 - supports longer responses
                system=self.system_prompt,
                tools=TOOLS,
                messages=messages,
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
        
        return {
            "response": final_response,
            "iterations": iteration,
        }

