"""WebSocket proxy for Deepgram FLUX streaming."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from starlette.websockets import WebSocketState

from app.core.settings import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)


async def _close_safely(
    ws: WebSocket | websockets.WebSocketClientProtocol | None,
    *,
    code: int = 1000,
    reason: str | None = None,
) -> None:
    """Attempt to close any websocket without raising."""
    if ws is None:
        return

    try:
        if isinstance(ws, WebSocket):
            await ws.close(code=code, reason=reason)
        else:
            await ws.close(code=code)
    except Exception:
        pass


async def _pipe_client_to_deepgram(
    client_ws: WebSocket,
    deepgram_ws: websockets.WebSocketClientProtocol,
) -> None:
    """Forward audio frames (binary) or text messages from the browser to Deepgram."""
    try:
        while True:
            message: dict[str, Any] = await client_ws.receive()
            if "bytes" in message and message["bytes"] is not None:
                await deepgram_ws.send(message["bytes"])
            elif "text" in message and message["text"] is not None:
                await deepgram_ws.send(message["text"])
            else:
                break
    except WebSocketDisconnect:
        logger.info("Client websocket disconnected")
    except Exception as exc:  # pragma: no cover - diagnostic path
        logger.exception("Error piping browser->Deepgram data: %s", exc)


async def _pipe_deepgram_to_client(
    client_ws: WebSocket,
    deepgram_ws: websockets.WebSocketClientProtocol,
) -> None:
    """Forward Deepgram responses to the browser as text JSON."""
    try:
        async for message in deepgram_ws:
            if isinstance(message, (bytes, bytearray)):
                try:
                    await client_ws.send_text(message.decode("utf-8"))
                except UnicodeDecodeError:
                    await client_ws.send_bytes(message)
            else:
                await client_ws.send_text(str(message))
    except WebSocketDisconnect:
        logger.info("Client websocket closed while sending Deepgram payloads")
    except Exception as exc:  # pragma: no cover - diagnostic path
        logger.exception("Error piping Deepgram->browser data: %s", exc)


@router.websocket("/flux")
async def proxy_flux(websocket: WebSocket) -> None:
    """Proxy websocket between the browser and Deepgram's FLUX API."""
    settings = get_settings()

    if not settings.deepgram_api_key:
        logger.error("Deepgram API key missing – aborting websocket")
        await websocket.close(
            code=status.WS_1011_INTERNAL_ERROR,
            reason="Deepgram API key not configured on server",
        )
        return

    await websocket.accept()

    query_string = websocket.url.query
    deepgram_url = "wss://api.deepgram.com/v2/listen"
    if query_string:
        deepgram_url = f"{deepgram_url}?{query_string}"

    logger.info("Opening Deepgram FLUX connection: %s", deepgram_url)

    try:
        deepgram_ws = await websockets.connect(
            deepgram_url,
            extra_headers={"Authorization": f"Token {settings.deepgram_api_key}"},
        )
    except Exception as exc:  # pragma: no cover - network failure path
        logger.exception("Failed to connect to Deepgram FLUX: %s", exc)
        await websocket.close(
            code=status.WS_1011_INTERNAL_ERROR,
            reason=f"Failed to connect to Deepgram: {exc}",
        )
        return

    forward_to_deepgram = asyncio.create_task(_pipe_client_to_deepgram(websocket, deepgram_ws))
    forward_to_client = asyncio.create_task(_pipe_deepgram_to_client(websocket, deepgram_ws))

    logger.info("Deepgram connection established; awaiting streaming")

    try:
        done, pending = await asyncio.wait(
            {forward_to_deepgram, forward_to_client},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for completed in done:
            try:
                completed.result()
            except WebSocketDisconnect:
                logger.info("Websocket disconnect detected; shutting down proxy")
            except Exception as exc:  # pragma: no cover - diagnostic path
                logger.exception("Proxy task ended with error: %s", exc)
    except Exception as exc:  # pragma: no cover - diagnostic path
        logger.exception("Unexpected error during streaming: %s", exc)
    finally:
        tasks = [forward_to_deepgram, forward_to_client]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        close_code = getattr(deepgram_ws, "close_code", None)
        close_reason = getattr(deepgram_ws, "close_reason", None)

        if close_code:
            logger.info(
                "Deepgram websocket closed with code=%s reason=%s",
                close_code,
                close_reason,
            )

        await _close_safely(deepgram_ws)

        if (
            websocket.application_state == WebSocketState.CONNECTED
            and close_code
            and close_code != 1000
        ):
            await _close_safely(websocket, code=close_code, reason=close_reason)
        else:
            await _close_safely(websocket)

