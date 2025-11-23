#!/usr/bin/env python3
"""
Complete Groq implementation for orchestrator.py
This adds full streaming and tool calling support for Groq.
"""

import re

def add_groq_to_process_query():
    """Add complete Groq streaming implementation to process_query method."""
    
    with open('app/agent/orchestrator.py', 'r') as f:
        content = f.read()
    
    # Find the iteration loop start in process_query
    # We need to add the Groq implementation right after iteration starts
    
    # Pattern to find: "# Stream response from Claude"
    pattern = r'(\s+)# Stream response from Claude with prompt caching'
    
    groq_implementation = r'''\1# Check provider and use appropriate streaming
\1if self.provider == "groq":
\1    # ====================
\1    # GROQ STREAMING
\1    # ====================
\1    # Convert tools to OpenAI format
\1    groq_tools = []
\1    for tool in TOOLS:
\1        groq_tools.append({
\1            "type": "function",
\1            "function": {
\1                "name": tool["name"],
\1                "description": tool["description"],
\1                "parameters": tool["input_schema"]
\1            }
\1        })
\1    
\1    # Convert messages to simple format
\1    groq_messages = []
\1    for msg in messages:
\1        if isinstance(msg["content"], str):
\1            groq_messages.append(msg)
\1        elif isinstance(msg["content"], list):
\1            # Extract text from complex content
\1            text_parts = []
\1            for block in msg["content"]:
\1                if block.get("type") == "text":
\1                    text_parts.append(block["text"])
\1            if text_parts:
\1                groq_messages.append({
\1                    "role": msg["role"],
\1                    "content": " ".join(text_parts)
\1                })
\1    
\1    # Add system message at start
\1    groq_messages_with_system = [
\1        {"role": "system", "content": self.system_prompt}
\1    ] + groq_messages
\1    
\1    # Call Groq streaming API
\1    try:
\1        stream = self.client.chat.completions.create(
\1            model=self.model,
\1            messages=groq_messages_with_system,
\1            tools=groq_tools if groq_tools else None,
\1            tool_choice="auto" if groq_tools else None,
\1            max_tokens=1024,
\1            temperature=0.7,
\1            stream=True
\1        )
\1        
\1        # Track tool calls during streaming
\1        current_tool_calls = {}
\1        
\1        for chunk in stream:
\1            if not chunk.choices:
\1                continue
\1            
\1            choice = chunk.choices[0]
\1            delta = choice.delta
\1            
\1            # Handle text content
\1            if delta.content:
\1                iteration_text += delta.content
\1            
\1            # Handle tool calls
\1            if delta.tool_calls:
\1                for tool_call_delta in delta.tool_calls:
\1                    idx = tool_call_delta.index
\1                    if idx not in current_tool_calls:
\1                        current_tool_calls[idx] = {
\1                            "id": tool_call_delta.id or "",
\1                            "name": tool_call_delta.function.name or "",
\1                            "arguments": ""
\1                        }
\1                    
\1                    if tool_call_delta.id:
\1                        current_tool_calls[idx]["id"] = tool_call_delta.id
\1                    if tool_call_delta.function.name:
\1                        current_tool_calls[idx]["name"] = tool_call_delta.function.name
\1                        yield {
\1                            "type": "tool_use_start",
\1                            "tool": tool_call_delta.function.name,
\1                        }
\1                    if tool_call_delta.function.arguments:
\1                        current_tool_calls[idx]["arguments"] += tool_call_delta.function.arguments
\1        
\1        # Process completed tool calls
\1        for tool_call in current_tool_calls.values():
\1            if not tool_call["name"]:
\1                continue
\1            
\1            # Parse arguments
\1            try:
\1                tool_input = json.loads(tool_call["arguments"]) if tool_call["arguments"] else {}
\1            except json.JSONDecodeError:
\1                logger.error(f"Failed to parse Groq tool args: {tool_call['arguments']}")
\1                tool_input = {}
\1            
\1            logger.info(f"🔧 Groq tool call: {tool_call['name']}({json.dumps(tool_input, indent=2)})")
\1            
\1            yield {
\1                "type": "tool_use",
\1                "tool": tool_call["name"],
\1                "input": tool_input,
\1            }
\1            
\1            # Execute tool
\1            try:
\1                tool_result = execute_tool(tool_call["name"], tool_input, self.db)
\1            except Exception as e:
\1                logger.error(f"Tool execution failed: {e}")
\1                tool_result = {"success": False, "error": str(e)}
\1            
\1            logger.info(f"✅ Groq tool result: {json.dumps(tool_result, indent=2)[:200]}...")
\1            
\1            yield {
\1                "type": "tool_result",
\1                "tool": tool_call["name"],
\1                "result": tool_result,
\1            }
\1            
\1            # Track for saving
\1            iteration_tool_calls.append(tool_call["name"])
\1            all_tool_calls.append({
\1                "id": tool_call["id"],
\1                "name": tool_call["name"],
\1                "input": tool_input,
\1            })
\1            all_tool_results.append({
\1                "tool_use_id": tool_call["id"],
\1                "content": json.dumps(tool_result),
\1            })
\1            
\1            # Add to messages for next iteration
\1            messages.append({
\1                "role": "assistant",
\1                "content": [{
\1                    "type": "tool_use",
\1                    "id": tool_call["id"],
\1                    "name": tool_call["name"],
\1                    "input": tool_input,
\1                }],
\1            })
\1            
\1            messages.append({
\1                "role": "user",
\1                "content": [{
\1                    "type": "tool_result",
\1                    "tool_use_id": tool_call["id"],
\1                    "content": json.dumps(tool_result),
\1                }],
\1            })
\1        
\1        # Token tracking (estimated for Groq)
\1        total_input_tokens += len(str(groq_messages_with_system)) // 4
\1        total_output_tokens += len(iteration_text) // 4
\1        
\1        has_tool_use = bool(iteration_tool_calls)
\1        has_text = bool(iteration_text.strip())
\1        
\1    except Exception as e:
\1        logger.error(f"Groq streaming error: {e}")
\1        raise
\1
\1else:
\1    # ====================
\1    # ANTHROPIC STREAMING
\1    # ====================
\1    # Stream response from Claude with prompt caching'''
    
    # Replace the comment with the full implementation
    content = re.sub(pattern, groq_implementation, content, count=1)
    
    return content

def add_groq_cost_tracking():
    """Update _save_cost to handle both providers."""
    
    with open('app/agent/orchestrator.py', 'r') as f:
        content = f.read()
    
    # Find and replace the cost calculation in _save_cost
    old_cost_calc = r'total_tokens = input_tokens \+ output_tokens\s+# Calculate costs \(per million tokens\)'
    
    new_cost_calc = '''total_tokens = input_tokens + output_tokens
            
            # Calculate costs based on provider
            if self.provider == "groq":
                # Groq pricing (free during beta)
                input_cost = (input_tokens / 1_000_000) * GROQ_INPUT_TOKEN_COST_PER_MILLION
                output_cost = (output_tokens / 1_000_000) * GROQ_OUTPUT_TOKEN_COST_PER_MILLION
                total_cost = input_cost + output_cost
            else:
                # Anthropic pricing
                # Calculate costs (per million tokens)'''
    
    content = re.sub(old_cost_calc, new_cost_calc, content)
    
    # Also update the actual cost calculation
    old_anthropic_calc = r'regular_input_cost = \(input_tokens / 1_000_000\) \* ANTHROPIC_INPUT_TOKEN_COST_PER_MILLION'
    new_anthropic_calc = '''regular_input_cost = (input_tokens / 1_000_000) * ANTHROPIC_INPUT_TOKEN_COST_PER_MILLION'''
    
    # Make sure it's indented properly (within else block)
    content = re.sub(
        r'(\s+)# These are the TOTAL costs.*?\n\s+regular_input_cost',
        r'\1# These are the TOTAL costs across all iterations INCLUDING cache costs\n\1    regular_input_cost',
        content
    )
    
    return content

if __name__ == "__main__":
    print("📝 Adding complete Groq implementation...")
    
    # Step 1: Add Groq streaming to process_query
    content = add_groq_to_process_query()
    
    with open('app/agent/orchestrator.py', 'w') as f:
        f.write(content)
    
    print("✅ Added Groq streaming implementation")
    
    # Step 2: Fix cost tracking
    content = add_groq_cost_tracking()
    
    with open('app/agent/orchestrator.py', 'w') as f:
        f.write(content)
    
    print("✅ Updated cost tracking")
    print("✅ Groq integration complete!")
    print("\n🔥 Now restart your server and Groq will work!")

