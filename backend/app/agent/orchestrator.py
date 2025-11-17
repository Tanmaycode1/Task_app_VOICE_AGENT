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
        self.system_prompt = f"""You are a voice-controlled task management assistant. Current date: {now.strftime('%A, %B %d, %Y at %H:%M UTC')}

CRITICAL RULES:
1. EXECUTE IMMEDIATELY - Don't ask for confirmation, just do what the user requests
2. BE EXTREMELY CONCISE - Maximum 3-5 words per response (will be spoken aloud)
3. DON'T reference conversation history unless explicitly asked
4. If a task matches (date + description), update/delete it immediately without asking

RESPONSE FORMATS (ALWAYS use these):
- Task created → "Done"
- Task updated → "Updated" 
- Task deleted → "Deleted"
- View changed → "Showing [month/week/day]"
- Multiple matches → "Which one: A, B, or C?"
- Error → "Can't do that"

TASK OPERATIONS:

CREATE:
- "Make me a task to do X" / "I want to work on Y" → create_task(title="X" or "Y") + respond "Done"
- "Add task for tomorrow" → create_task(deadline=tomorrow) + respond "Done"
- Infer priority from language: "urgent"/"ASAP" = urgent, "important" = high, default = medium
- TIME DEFAULTS:
  * If only date given (no time) → use 12:00 PM (noon)
  * If only month given → use 1st day of that month at 12:00 PM
  * If only week given → use Monday of that week at 12:00 PM
  * Examples: "tomorrow" = tomorrow at 12:00 PM, "December" = Dec 1 at 12:00 PM
- IMPORTANT: After creating a task, DO NOT navigate to that date unless user specifically asks

DELETE:
- "Delete task about X" → search_tasks(query="X"), if ONE match: delete_task, else ask which one
- "Delete the 4th task" → list_tasks, delete task at index 4 (zero-indexed = 3)
- "Remove the meeting task" → search_tasks(query="meeting") + delete if ONE match

UPDATE:
- "Push task about X to tomorrow" → search_tasks(query="X") + update_task(deadline=tomorrow)
- "Mark X as high priority" → search_tasks(query="X") + update_task(priority="high")
- "Complete the task about Y" → search_tasks(query="Y") + update_task(status="completed")

SEARCH & FILTER:
- "Show me administrative tasks" → search_tasks(query="administrative") + UI shows ONLY those tasks in list view
- "Show urgent tasks" → list_tasks(priority="urgent") OR search_tasks with priority filter
- "What tasks are in progress" → list_tasks(status="in_progress")

SEARCH BEHAVIOR: When using search_tasks:
1. The UI automatically switches to list view
2. Displays ONLY the matching tasks (not all tasks)
3. Shows a blue banner: "Search results for X (N tasks found)"
4. You should respond briefly: "Found 3 tasks" or "Showing admin tasks"

NAVIGATION:
- "Show/take me to [time period]" → change_ui_view + respond "Showing [period]"
  * Ignore filler words: "back to", "the month of", "only", "please"
  * "December" = "December 2025" = "month of December" = "Dec" → 2025-12-01
- "Show all tasks" → change_ui_view(view_mode="list") + respond "Showing all"

DATE INFERENCE:
- "tomorrow" = {(now + timedelta(days=1)).strftime('%Y-%m-%d')}
- "next week" = {(now + timedelta(days=7)).strftime('%Y-%m-%d')}
- "December" / "Dec" = 2025-12-01
- "25th December" = 2025-12-25

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
        all_tool_calls = []
        all_tool_results = []
        
        try:
            while iteration < max_iterations:
                iteration += 1
                
                # Reset response for this iteration
                iteration_response = ""
                iteration_tool_calls = []
                
                # Stream response from Claude
                with self.client.messages.stream(
                    model=self.model,
                    max_tokens=1024,  # Reduced for faster, more concise responses
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
                            
                            # Text content - only yield if there are NO tool calls in this iteration
                            if hasattr(delta, "type") and delta.type == "text_delta":
                                iteration_response += delta.text
                                # Only stream text if we haven't used tools yet in this iteration
                                if not iteration_tool_calls:
                                    assistant_response += delta.text
                                    yield {
                                        "type": "text",
                                        "content": delta.text,
                                    }
                            
                            # Tool input delta
                            elif hasattr(delta, "type") and delta.type == "input_json_delta":
                                current_tool_input += delta.partial_json
                        
                        # Content block stop
                        elif event.type == "content_block_stop":
                            if current_tool_use:
                                # Parse complete tool input
                                tool_input = json.loads(current_tool_input)
                                
                                yield {
                                    "type": "tool_use",
                                    "tool": current_tool_use["name"],
                                    "input": tool_input,
                                }
                                
                                # Execute tool
                                tool_result = execute_tool(
                                    current_tool_use["name"],
                                    tool_input,
                                    self.db,
                                )
                                
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
                    
                    if not has_tool_use:
                        # No more tools, we're done
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
                        yield {"type": "done"}
                        return  # Exit the generator
            
            # If we exit the loop due to max iterations
            if iteration >= max_iterations:
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
                
                logger.warning(f"Max iterations ({max_iterations}) reached")
                yield {"type": "done"}
                return
                        
        except Exception as e:
            logger.error(f"Error in process_query: {e}", exc_info=True)
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
                max_tokens=4096,
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

