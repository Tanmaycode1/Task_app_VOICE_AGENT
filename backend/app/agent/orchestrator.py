"""Agent orchestrator with Gemini 3 Flash and streaming support."""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import AsyncGenerator, Any

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.agent.tools import TOOLS, execute_tool
from app.models.conversation import ConversationMessage

logger = logging.getLogger(__name__)


class TaskAgent:
    """Agent for managing tasks using Gemini with tool calling."""

    def __init__(self, db: Session):
        self.db = db
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")

        self.model = "gemini-3-flash-preview"
        self.client = genai.Client(api_key=api_key)
        self.gemini_tools = self._build_gemini_tools(TOOLS)
        
        # Build system prompt with current date/time
        now = datetime.utcnow()
        current_time_str = now.strftime('%H:%M')
        current_date_str = now.strftime('%A, %B %d, %Y at %H:%M UTC')
        tomorrow_str = (now + timedelta(days=1)).strftime('%Y-%m-%d')
        next_week_str = (now + timedelta(days=7)).strftime('%Y-%m-%d')
        
        self.system_prompt = f"""You are a voice-controlled task manager. Current date: {current_date_str} (time: {current_time_str}).

CORE RULES:
1. Be decisive and concrete. Execute immediately unless truly ambiguous.
2. Be extremely concise: 3-5 words max (spoken output).
3. Do not reference history unless asked.
4. Single response only: tool call(s) + final text in the same assistant message.
5. Handle ambiguity intelligently; offer choices when needed.

MEMORY / HISTORY:
- Last 5 messages are auto-loaded globally.
- Use load_full_history only when needed for relevant older context (semantic, typo-tolerant ranking by keyword/tool, with low recency weight).
- Extract keywords from user query; use targeted search_terms and tool filters.
- For revert/restore/approve-plan/previous-options questions, search then act immediately.
- Do not say "I need to check"; do it.
- Avoid empty search_terms unless pure recency is intended.
- Usually do NOT use history for normal create/update/delete/list/search or view changes.

RESPONSE SHAPES:
- Created: "Done" / "Created N tasks"
- Updated: "Updated" / "Updated N tasks"
- Deleted: "Deleted" / "Deleted N tasks"
- View change: "Showing [month/week/day]"
- Create/update with date navigation: combine result + "Showing [...]"
- 2-3 matches: "Which one: A) ..., B) ...?"
- 4+ matches: "Delete all or pick one?" / "Update all or pick one?"
- Partial completion ambiguity: "Mark complete or split?"
- Split success: "Split and marked"
- Not found/invalid: "Can't find that" / "Can't do that"

TOOL USAGE:
- Always call tools and provide final text together in one turn.
- Never do tool call first and answer later.
- Prefer bulk tools when possible: create_multiple_tasks, update_multiple_tasks, delete_multiple_tasks.

CREATE:
- Single: create_task + "Done"
- Multiple: create_multiple_tasks + "Created N tasks"
- Priority inference: urgent/ASAP=urgent, important=high, else medium.
- Missing schedule: if no day/time/date/month/week is provided, ask: "When do you want me to schedule this for?"
- scheduled_date is required planning date; deadline is optional hard due date.
- If one date mentioned, use scheduled_date (deadline None).
- If phrasing includes "by [date]" / "deadline [date]", separate scheduled_date vs deadline.
- Time defaults:
  * Date only -> 12:00 PM.
  * "tomorrow" without time -> tomorrow date with current HH:MM.
  * Month only -> 1st day, 12:00 PM.
  * Week only -> Monday, 12:00 PM.
- After create, navigate only when date is meaningfully away:
  * Do NOT navigate for today, dates within current week, or unspecified date (unless explicitly asked to show).
  * DO navigate for next week/later, next month/specific future month, or >7 days away.

DELETE:
- If exactly one clear match, delete immediately.
- If 2+ matches, use show_choices modal with ALL matches labeled A/B/C... .
- If 5+ matches, add an "All" option (value "delete_all").
- If 0 matches: "Can't find that".
- For "which options did you show?" / similar:
  * If not in last 5 messages, call load_full_history(limit=2), find show_choices, then explain.
- Deletion navigation rule:
  * Navigate ONLY if user explicitly mentions date/week/month in delete query.
  * Map mention to daily/weekly/monthly view accordingly.
- Revert deleted task:
  * load_full_history with delete-focused keywords/tool filter.
  * Read original_state from tool_results.
  * Recreate task with all original fields.
  * Respond "Restored".

UPDATE:
- If one clear match, update immediately.
- If 2+ matches, use show_choices with ALL matches; add "All" if 5+.
- If 0 matches: "Can't find that".
- For prior update/options questions, use load_full_history with targeted keywords/tools and explain decisively.
- Partial completion / multi-item task handling:
  * Detect multi-item titles (and/or/comma lists) when user reports completing only some items.
  * Ask via show_choices:
    - Complete: mark whole task completed.
    - Split: split into completed items task + remaining items task.
  * If split:
    1) Keep original metadata (scheduled_date/deadline/priority).
    2) Create completed task (status=completed, completed_at=now).
    3) Create remaining task (status=todo).
    4) Delete original task.
    5) Navigate to weekly view of original scheduled date.
    6) Respond "Split and marked".
  * Do all split steps in one response.
  * Do NOT ask when user explicitly says mark complete, or task has one item, or all items are done.
- Date shifting:
  * next week=+7 days, next month=+30 days, tomorrow=+1 day, next weekday=nearest forward occurrence.
  * If shifted scheduled_date goes past existing deadline, ask:
    "The new schedule (X date) is after the deadline (Y date). Should I move the deadline too?"
  * If user confirms, shift scheduled_date and deadline by same amount.
- After scheduled_date update, auto-navigate by requested period:
  * day/today/tomorrow/specific date -> daily
  * week/this week/next week/day-name planning -> weekly
  * month/month-name -> monthly
  * No date change (status/priority only) -> no navigation.
- Revert updates:
  * load_full_history(update-focused)
  * extract original_state
  * update_task with all original fields
  * respond "Reverted"

SEARCH / FILTER:
- search_tasks for text queries (results already list-oriented).
- change_ui_view(list) supports combined filters:
  filter_status, filter_priority, filter_missed ("missed"/"not_missed"), filter_start_date, filter_end_date.
- list_tasks supports has_deadline true/false and date-bound retrieval.
- Apply only requested filters.

NARRATE + NAVIGATE ("what are my tasks for X"):
- Always do both:
  1) list tasks for the period,
  2) narrate naturally (count + task titles, include time if specific, mention high/urgent priority),
  3) navigate to matching view (daily/weekly/monthly).

WEEK PLANNING / GOAL BREAKDOWN:
- Detect planning intents ("plan my week", "break down", "organize", etc.).
- Workflow:
  1) Parse constraints:
     - hours/day from user (default 1-2),
     - unavailable days (default exclude weekends).
  2) Break goal into logical subtasks (research/design/implement/test/review style), each ~1-2 hours.
  3) Distribute across available days evenly, honoring dependencies and priorities.
  4) Start-date logic:
     - "plan my week"/"plan next week"/"plan the week" -> next Monday.
     - "plan this week" -> this Monday (or today if Monday passed).
     - explicit "starting/from [day]" -> that specific day.
  5) Show plan with show_choices:
     - numbered task entries (read-only display),
     - then action entries: Approve / Edit / Reject (always at end).
  6) Wait for user response after showing plan; never auto-create.
  7) On Approve/yes/create:
     - If needed, load_full_history(plan-focused) to recover plan.
     - create_multiple_tasks with ALL planned tasks (all-or-nothing).
     - Task format: title + scheduled_date (ISO "YYYY-MM-DDTHH:MM:SS"), optional priority/deadline.
     - Navigate weekly to first plan day.
     - Respond "Planned and created".
  8) On Edit/change:
     - Ask what to change, regenerate, show updated plan, repeat.
  9) On Reject/cancel/no:
     - Respond "Planning cancelled"; create nothing.
- Keep track of planned task details until approval.
- Distribution guidance: large goals ~8-10 tasks, small goals ~3-5, avoid overloading a day.

NAVIGATION:
- "Show/take me to [period]" -> change_ui_view + "Showing [period]".
- Ignore fillers like "back to", "the month of", "only", "please".
- "Show all tasks" -> change_ui_view(view_mode="list").

CALENDAR LOGIC:
- Calendar placement uses scheduled_date.
- If deadline exists, show both scheduled date and deadline.
- Missed = current date > deadline and status != completed.

DATE INFERENCE:
- "tomorrow" = {tomorrow_str}
- "next week" = {next_week_str}
- "December"/"Dec" = 2025-12-01
- "25th December" = 2025-12-25

RELATIVE WEEKDAY RULE:
- Use nearest forward occurrence from today.
- Keep original time if present; else 12:00 PM.
- Algorithm:
  1) current weekday (0=Mon...6=Sun)
  2) target weekday
  3) days_ahead = (target-current) % 7; if 0 -> 7
  4) add days_ahead

INDEX-BASED REQUESTS:
1. Call list_tasks for current view.
2. User speaks 1-indexed; data is 0-indexed.
3. Act on selected task_id.

STYLE RESTRICTION:
- Never say: "I'll", "Let me", "I'm going to", "I can", "I will". Return result directly."""

    @staticmethod
    def _build_gemini_tools(tools: list[dict[str, Any]]) -> list[types.Tool]:
        """Convert internal tool schema format to Gemini function declarations."""
        function_declarations = [
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
            }
            for tool in tools
        ]
        return [types.Tool(function_declarations=function_declarations)]

    @staticmethod
    def _to_gemini_contents(history: list[dict]) -> list[dict[str, Any]]:
        """Convert stored conversation history into Gemini contents format."""
        contents: list[dict[str, Any]] = []
        for msg in history:
            role = msg.get("role")
            content = msg.get("content")
            if role not in {"user", "assistant"}:
                continue
            target_role = "model" if role == "assistant" else "user"

            # Plain text content
            if isinstance(content, str) and content.strip():
                contents.append({"role": target_role, "parts": [{"text": content}]})
                continue

            # Block content: keep only text blocks as conversational context
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        if text:
                            text_parts.append(text)
                if text_parts:
                    contents.append({"role": target_role, "parts": [{"text": "\n".join(text_parts)}]})

        return contents

    def _load_conversation_history(self, limit: int = 5) -> list[dict]:
        """
        Load recent conversation history from database (global, no session filtering).
        
        Formats messages with text, tool calls, and tool results.
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
        
        # Build model messages from conversation history
        contents = self._to_gemini_contents(conversation_history or [])
        contents.append({"role": "user", "parts": [{"text": user_query}]})
        
        # Debug: log message format
        logger.info(f"Processing query with {len(contents)} contents in history")
        
        # Immediately yield a "thinking" event to show we're processing
        yield {
            "type": "thinking",
            "content": "Processing your request...",
        }
        
        max_iterations = 5  # Prevent infinite loops and keep latency low
        iteration = 0
        assistant_response = ""
        all_tool_calls = []
        all_tool_results = []
        
        try:
            while iteration < max_iterations:
                iteration += 1
                
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        tools=self.gemini_tools,
                        max_output_tokens=4096,
                    ),
                )

                # Gather plain text from model parts
                iteration_text_parts: list[str] = []
                candidate_content = None
                if response.candidates:
                    candidate_content = response.candidates[0].content
                    for part in (candidate_content.parts or []):
                        part_text = getattr(part, "text", None)
                        if part_text:
                            iteration_text_parts.append(part_text)
                iteration_text = "".join(iteration_text_parts).strip()

                # Gather function calls (SDK helper first, then fallback from parts)
                tool_calls = list(getattr(response, "function_calls", None) or [])
                if not tool_calls and response.candidates:
                    for part in (response.candidates[0].content.parts or []):
                        fc = getattr(part, "function_call", None)
                        if fc:
                            tool_calls.append(fc)

                if tool_calls:
                    function_response_parts = []
                    for idx, tool_call in enumerate(tool_calls):
                        tool_name = tool_call.name
                        tool_call_id = f"call_{iteration}_{idx}"
                        raw_args_obj = tool_call.args or {}

                        yield {
                            "type": "tool_use_start",
                            "tool": tool_name,
                        }

                        try:
                            if isinstance(raw_args_obj, str):
                                tool_input = json.loads(raw_args_obj) if raw_args_obj.strip() else {}
                            else:
                                tool_input = dict(raw_args_obj)
                        except Exception:
                            logger.error(f"Failed to parse tool input for {tool_name}: {raw_args_obj!r}")
                            tool_input = {}

                        yield {
                            "type": "tool_use",
                            "tool": tool_name,
                            "input": tool_input,
                        }

                        try:
                            tool_result = execute_tool(tool_name, tool_input, self.db)
                        except Exception as e:
                            logger.error(f"Tool execution failed for {tool_name}: {e}")
                            tool_result = {
                                "success": False,
                                "error": f"Tool execution failed: {str(e)}",
                            }

                        yield {
                            "type": "tool_result",
                            "tool": tool_name,
                            "result": tool_result,
                        }

                        all_tool_calls.append({
                            "id": tool_call_id,
                            "name": tool_name,
                            "input": tool_input,
                        })
                        all_tool_results.append({
                            "tool_use_id": tool_call_id,
                            "content": json.dumps(tool_result),
                        })

                        function_response_parts.append({
                            "functionResponse": {
                                "name": tool_name,
                                "response": {"result": tool_result},
                            }
                        })

                    if candidate_content:
                        contents.append(candidate_content)
                    elif iteration_text:
                        contents.append({"role": "model", "parts": [{"text": iteration_text}]})
                    contents.append({"role": "user", "parts": function_response_parts})

                    # Gemini can return text and tool calls together.
                    if iteration_text:
                        assistant_response = iteration_text
                        for char in iteration_text:
                            yield {"type": "text", "content": char}

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
                        yield {"type": "done"}
                        return

                    continue

                # No tool calls means this is the final text response.
                if iteration_text:
                    assistant_response = iteration_text
                    for char in iteration_text:
                        yield {"type": "text", "content": char}

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

                yield {"type": "done"}
                return
            
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
        history = self._to_gemini_contents(self._load_conversation_history())
        contents = history + [{"role": "user", "parts": [{"text": user_query}]}]
        
        max_iterations = 5
        iteration = 0
        final_response = ""
        
        while iteration < max_iterations:
            iteration += 1

            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                    tools=self.gemini_tools,
                    max_output_tokens=4096,
                ),
            )

            candidate_content = response.candidates[0].content if response.candidates else None
            if candidate_content:
                for part in (candidate_content.parts or []):
                    if getattr(part, "text", None):
                        final_response += part.text

            tool_calls = list(getattr(response, "function_calls", None) or [])
            if not tool_calls and response.candidates:
                for part in (response.candidates[0].content.parts or []):
                    fc = getattr(part, "function_call", None)
                    if fc:
                        tool_calls.append(fc)
            if not tool_calls:
                break

            function_response_parts = []
            for tool_call in tool_calls:
                tool_name = tool_call.name
                raw_args_obj = tool_call.args or {}
                try:
                    if isinstance(raw_args_obj, str):
                        tool_input = json.loads(raw_args_obj) if raw_args_obj.strip() else {}
                    else:
                        tool_input = dict(raw_args_obj)
                except Exception:
                    tool_input = {}

                tool_result = execute_tool(tool_name, tool_input, self.db)
                function_response_parts.append({
                    "functionResponse": {
                        "name": tool_name,
                        "response": {"result": tool_result},
                    }
                })

            if candidate_content:
                contents.append(candidate_content)
            contents.append({"role": "user", "parts": function_response_parts})
        
        return {
            "response": final_response,
            "iterations": iteration,
        }

