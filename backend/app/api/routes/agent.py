"""Agent API endpoints with streaming support."""

import asyncio
import json
import logging
from typing import Any

import websockets
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.agent.orchestrator import TaskAgent
from app.core.settings import get_settings
from app.db.base import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/agent")
async def agent_websocket(websocket: WebSocket, db: Session = Depends(get_db)):
    """
    WebSocket endpoint for agent interaction with FLUX integration.
    Simplified with proper error handling and retries.
    """
    settings = get_settings()
    
    # Validate API keys
    if not settings.deepgram_api_key:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Deepgram API key not configured")
        return
    
    if not settings.anthropic_api_key:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Anthropic API key not configured")
        return
    
    await websocket.accept()
    logger.info("✅ Agent websocket connected")
    
    # Get session ID
    agent = TaskAgent(db)
    
    # Build Deepgram URL
    query_params = websocket.url.query or "model=flux-general-en&sample_rate=16000&encoding=linear16&eot_threshold=0.9"
    deepgram_url = f"wss://api.deepgram.com/v2/listen?{query_params}"
    
    deepgram_ws = None
    current_transcript = ""
    is_processing = False
    
    try:
        # Connect to Deepgram with retry
        for attempt in range(3):
            try:
                deepgram_ws = await websockets.connect(
                    deepgram_url,
                    extra_headers={"Authorization": f"Token {settings.deepgram_api_key}"},
                )
                logger.info("✅ Connected to Deepgram FLUX")
                break
            except Exception as e:
                if attempt == 2:
                    raise
                logger.warning(f"Deepgram connection attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(0.5)
        
        async def forward_audio():
            """Forward audio from client to Deepgram."""
            try:
                while True:
                    message = await websocket.receive()
                    
                    if "bytes" in message and message["bytes"]:
                        if deepgram_ws and deepgram_ws.open:
                            await deepgram_ws.send(message["bytes"])
                    
                    elif "text" in message:
                        data = json.loads(message["text"])
                        if data.get("type") == "close":
                            logger.info("Client requested close")
                            break
                            
            except WebSocketDisconnect:
                logger.info("Client disconnected")
            except Exception as e:
                logger.error(f"Audio forward error: {e}")
        
        async def process_deepgram():
            """Process Deepgram responses and trigger agent."""
            nonlocal current_transcript, is_processing
            
            try:
                async for message in deepgram_ws:
                    if not message or not message.strip():
                        continue
                    
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        continue
                    
                    # Forward FLUX event to client
                    await websocket.send_text(json.dumps({"type": "flux_event", "data": data}))
                    
                    # Handle TurnInfo events
                    if data.get("type") == "TurnInfo":
                        event = data.get("event")
                        transcript = data.get("transcript", "").strip()
                        
                        if transcript:
                            current_transcript = transcript
                        
                        # Process on EndOfTurn
                        if event == "EndOfTurn" and current_transcript and not is_processing:
                            is_processing = True
                            query = current_transcript
                            current_transcript = ""
                            
                            logger.info(f"🎤 Processing: {query}")
                            
                            # Signal start
                            await websocket.send_text(json.dumps({
                                "type": "agent_start",
                                "query": query
                            }))
                            
                            # Process with timeout and retry
                            for retry in range(2):
                                try:
                                    async def run_agent():
                                        event_count = 0
                                        async for event in agent.process_query(query):
                                            event_count += 1
                                            event_type = event.get("type", "unknown")
                                            
                                            # Log what we're sending
                                            if event_type == "text":
                                                logger.debug(f"📤 Sending text event: {event.get('content', '')[:50]}")
                                            elif event_type == "done":
                                                logger.info(f"📤 Sending 'done' event (total events: {event_count})")
                                            elif event_type == "tool_result":
                                                logger.info(f"📤 Sending tool_result for: {event.get('tool')}")
                                            
                                            await websocket.send_text(json.dumps({
                                                "type": "agent_event",
                                                "data": event
                                            }))
                                        
                                        logger.info(f"✅ Agent processing complete. Sent {event_count} events total")
                                    
                                    await asyncio.wait_for(run_agent(), timeout=30.0)
                                    break  # Success
                                    
                                except asyncio.TimeoutError:
                                    logger.error(f"⏱️ Timeout (attempt {retry + 1})")
                                    if retry == 1:
                                        await websocket.send_text(json.dumps({
                                            "type": "agent_error",
                                            "error": "Request timeout"
                                        }))
                                        await websocket.send_text(json.dumps({
                                            "type": "agent_event",
                                            "data": {"type": "done"}
                                        }))
                                    else:
                                        await asyncio.sleep(0.5)
                                        
                                except Exception as e:
                                    logger.error(f"❌ Agent error (attempt {retry + 1}): {e}")
                                    
                                    if retry == 1:
                                        # Note: History is global now, so we don't clear on error
                                        # to preserve context across all conversations
                                        logger.info("⚠️ Agent error - history preserved for context")
                                        
                                        await websocket.send_text(json.dumps({
                                            "type": "agent_error",
                                            "error": "Processing failed"
                                        }))
                                        await websocket.send_text(json.dumps({
                                            "type": "agent_event",
                                            "data": {"type": "done"}
                                        }))
                                    else:
                                        await asyncio.sleep(0.5)
                            
                            is_processing = False
                            
            except websockets.exceptions.ConnectionClosed:
                logger.info("Deepgram connection closed")
            except Exception as e:
                logger.error(f"Deepgram processing error: {e}")
        
        # Run concurrently
        audio_task = asyncio.create_task(forward_audio())
        deepgram_task = asyncio.create_task(process_deepgram())
        
        # Wait for first to complete
        done, pending = await asyncio.wait(
            [audio_task, deepgram_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Check for errors
        for task in done:
            try:
                task.result()
            except Exception as e:
                logger.error(f"Task error: {e}")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    
    finally:
        # Cleanup
        logger.info("🧹 Cleaning up...")
        
        for task in [audio_task, deepgram_task]:
            if not task.done():
                task.cancel()
        
        if deepgram_ws:
            try:
                await deepgram_ws.close()
            except Exception:
                pass
        
        try:
            await websocket.close()
        except Exception:
            pass
        
        logger.info("✅ Agent websocket closed")


@router.post("/agent/query")
async def agent_query(query: dict[str, str], db: Session = Depends(get_db)):
    """Simple HTTP endpoint for agent queries (non-streaming)."""
    settings = get_settings()
    
    if not settings.anthropic_api_key:
        return {"error": "Anthropic API key not configured"}
    
    user_query = query.get("query", "")
    if not user_query:
        return {"error": "Query is required"}
    
    agent = TaskAgent(db)
    result = agent.process_query_sync(user_query)
    
    return result
