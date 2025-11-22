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
        
        self.system_prompt = f"""Voice task assistant. Date: {current_date_str}, Time: {current_time_str}

CORE RULES:
1. Execute immediately, ask only if ambiguous
2. Max 3-5 words per response (spoken aloud)
3. Call tool(s) + text response in ONE message
4. Use bulk operations when possible

MEMORY:
- Auto: Last 3 messages loaded
- load_full_history: Semantic search for restore/revert/approve operations
  * Restore: load_full_history(search_terms=["delete"], tools=["delete_task"], limit=2) → extract original_state → create_task
  * Approve plan: load_full_history(search_terms=["plan"], tools=["show_choices"], limit=2) → create_multiple_tasks
  * Keywords from query: "restore meeting" → ["meeting", "delete"]
  * BE DECISIVE: search → act (no "I need to check")

RESPONSES:
- Created → "Done" / "Created N tasks"
- Updated → "Updated" / "Updated N tasks"
- Deleted → "Deleted" / "Deleted N tasks"
- Multiple matches → "Which: A) [title], B) [title]?"
- Many matches (4+) → "Delete all or pick?"
- Partial completion → "Mark complete or split?"
- Error → "Can't find that"

CREATE:
- Infer priority: "urgent"/"ASAP"=urgent, "important"=high, else medium
- No date mentioned → ask "When?"
- scheduled_date (required): when to do it
- deadline (optional): must be done by
- Time defaults: 12:00 PM, except "tomorrow" without time → keep current hour:minute
- Navigate only if >7 days away or explicit: "next week"→weekly view, "December"→monthly

DELETE:
- 1 match → delete immediately
- 2+ matches → show_choices with A,B,C labels + "All" option if 5+
- Navigate ONLY if date/week/month mentioned in query
- Restore: load_full_history(search_terms=[keywords,"delete"], tools=["delete_task"]) → find original_state → create_task

UPDATE:
- 1 match → update immediately
- 2+ matches → show_choices (like DELETE)
- Partial completion (multi-item task):
  * Detect: "buy X and Y" but user completed only X
  * show_choices: "Complete" vs "Split"
  * Split: create completed task (status="completed", completed_at=now) + remaining task (status="todo") → delete original → navigate to week → "Split and marked"
- Date shift: "next week"=+7d, "next month"=+30d, "Monday"=nearest Monday
- If new date > deadline → ask to move deadline
- Navigate after date change: day→daily, week→weekly, month→monthly
- Revert: load_full_history(search_terms=[keywords,"update"], tools=["update_task"]) → update with original fields

SEARCH:
- search_tasks(query) → auto list view
- Filters: change_ui_view(view_mode="list", filter_priority/status/missed, filter_start_date, filter_end_date)
- Multiple filters: "urgent next week" → filter_priority="urgent" + filter_start/end_date

NARRATE & NAVIGATE:
- "tasks for tomorrow" → list_tasks(scheduled_after/before) + narrate + change_ui_view(daily, tomorrow)
- "tasks next week" → list_tasks + narrate + change_ui_view(weekly, next_monday)

WEEK PLANNING:
1. Parse: hours/day (default 1-2h), unavailable days (default exclude weekends)
2. Break goal into subtasks (1-2h each)
3. Distribute: "plan my week" → start NEXT Monday, "plan this week" → this Monday/today
4. show_choices: numbered tasks (1,2,3...) + Approve/Edit/Reject
5. Wait for response:
   - Approve → load_full_history if needed → create_multiple_tasks (ISO 8601: "2025-01-13T12:00:00") → change_ui_view(weekly) → "Planned and created"
   - Edit → "What to change?" → regenerate → show again
   - Reject → "Planning cancelled"

NAVIGATION:
- "show tomorrow" → change_ui_view(daily, tomorrow)
- "show next week" → change_ui_view(weekly, next_monday)
- "show December" → change_ui_view(monthly, 2025-12-01)
- "show all" → change_ui_view(list)

DATES:
- tomorrow = {tomorrow_str}
- next week = {next_week_str}
- Relative days (Mon/Tue/etc): nearest forward occurrence
  * Today Wed Nov 12: "Monday" = Nov 17 (+5d), "Friday" = Nov 14 (+2d)
- Algorithm: (target_day - current_day) % 7, if 0 use 7

INDEX: "4th task" → list_tasks → use index 3 (0-indexed)

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
        cache_creation_tokens: int,
        cache_read_tokens: int,
        iterations: int,
        tool_calls_count: int,
    ):
        """Save API cost tracking to database.
        
        This method saves the TOTAL costs across all iterations for a single request.
        input_tokens, output_tokens, cache tokens should be the accumulated totals from all iterations.
        """
        try:
            total_tokens = input_tokens + output_tokens
            
            # Calculate costs (per million tokens)
            # These are the TOTAL costs across all iterations INCLUDING cache costs
            regular_input_cost = (input_tokens / 1_000_000) * INPUT_TOKEN_COST_PER_MILLION
            cache_write_cost = (cache_creation_tokens / 1_000_000) * CACHE_WRITE_COST_PER_MILLION
            cache_read_cost = (cache_read_tokens / 1_000_000) * CACHE_READ_COST_PER_MILLION
            input_cost = regular_input_cost + cache_write_cost + cache_read_cost
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
        total_cache_creation_tokens = 0
        total_cache_read_tokens = 0
        
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
                            total_cache_creation_tokens += cache_creation_tokens
                            total_cache_read_tokens += cache_read_tokens
                            
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
                            cache_creation_tokens=total_cache_creation_tokens,
                            cache_read_tokens=total_cache_read_tokens,
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
                            cache_creation_tokens=total_cache_creation_tokens,
                            cache_read_tokens=total_cache_read_tokens,
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
                    cache_creation_tokens=total_cache_creation_tokens,
                    cache_read_tokens=total_cache_read_tokens,
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
                    cache_creation_tokens=total_cache_creation_tokens,
                    cache_read_tokens=total_cache_read_tokens,
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
        total_cache_creation_tokens = 0
        total_cache_read_tokens = 0
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
                total_cache_creation_tokens += cache_creation_tokens
                total_cache_read_tokens += cache_read_tokens
                
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
            cache_creation_tokens=total_cache_creation_tokens,
            cache_read_tokens=total_cache_read_tokens,
            iterations=iteration,
            tool_calls_count=len(all_tool_calls),
        )
        
        return {
            "response": final_response,
            "iterations": iteration,
        }

