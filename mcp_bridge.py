import asyncio
import threading
from typing import Any

from fastmcp import Client


MCP_SERVER = "mcp_server.py"

_client = None
_loop = None
_thread = None
_ready = threading.Event()
_startup_error = None


async def _client_loop():
    global _client, _startup_error

    try:
        _client = Client(MCP_SERVER)

        async with _client:
            await _client.ping()
            _ready.set()

            # Keep the MCP connection alive
            await asyncio.Event().wait()

    except BaseException as exc:
        _startup_error = exc
        _ready.set()


def _start_mcp_client():
    global _loop, _thread

    if _thread is not None and _thread.is_alive():
        return

    def runner():
        global _loop

        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)

        try:
            _loop.run_until_complete(_client_loop())
        finally:
            _loop.close()

    _thread = threading.Thread(
        target=runner,
        daemon=True,
        name="mcp-client",
    )

    _thread.start()

    _ready.wait()

    if _startup_error is not None:
        raise RuntimeError(
            f"MCP client failed to start: {_startup_error}"
        )


async def _call_tool(
    tool_name: str,
    arguments: dict[str, Any],
):
    result = await _client.call_tool(
        tool_name,
        arguments,
    )

    if result.data is not None:
        return str(result.data)

    if result.content:
        parts = []

        for item in result.content:
            text = getattr(item, "text", None)

            if text is not None:
                parts.append(str(text))
            else:
                parts.append(str(item))

        return "\n".join(parts)

    return str(result)


def call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
) -> str:

    _start_mcp_client()

    future = asyncio.run_coroutine_threadsafe(
        _call_tool(
            tool_name,
            arguments,
        ),
        _loop,
    )

    return future.result()