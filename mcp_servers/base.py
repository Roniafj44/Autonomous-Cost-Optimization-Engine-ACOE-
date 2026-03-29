"""
ACOE — MCP Base Server Framework
=================================
A lightweight, zero-dependency MCP server implementation using JSON-RPC 2.0
over stdio. Compatible with Python 3.9+.

This is the foundation for all ACOE MCP servers. It handles:
  - JSON-RPC request parsing and response formatting
  - MCP protocol handshake (initialize, initialized, tools/list)
  - Tool registration and dispatch
  - Comprehensive error handling so no request ever crashes the server

MCP Protocol Reference:
  https://modelcontextprotocol.io/docs/concepts/transports
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("acoe.mcp.base")


# ── JSON-RPC Error Codes ─────────────────────────────────────────────────────

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class MCPTool:
    """Descriptor for a registered MCP tool."""

    def __init__(
        self,
        name: str,
        description: str,
        handler: Callable,
        input_schema: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.description = description
        self.handler = handler
        # JSON Schema for the tool's input parameters
        self.input_schema = input_schema or {"type": "object", "properties": {}}

    def to_mcp_format(self) -> dict:
        """Serialize this tool descriptor to the MCP tools/list format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class MCPBaseServer:
    """
    Lightweight MCP server using JSON-RPC 2.0 over stdio.

    Subclasses register tools via `self.register_tool(...)` and then
    call `self.run()` to enter the message loop.

    Every possible failure point is wrapped in try/except to ensure
    the server NEVER crashes — it always returns a valid JSON-RPC
    error response instead.
    """

    # MCP protocol version we support
    PROTOCOL_VERSION = "2024-11-05"

    def __init__(self, name: str, version: str = "1.0.0", description: str = ""):
        self.name = name
        self.version = version
        self.description = description
        self._tools: Dict[str, MCPTool] = {}
        self._initialized = False

        # Configure logging to stderr so it doesn't pollute stdout (JSON-RPC channel)
        logging.basicConfig(
            level=logging.INFO,
            format=f"[{name}] %(levelname)s %(message)s",
            stream=sys.stderr,
        )

    # ── Tool Registration ────────────────────────────────────────────────

    def register_tool(
        self,
        name: str,
        description: str,
        handler: Callable,
        input_schema: Optional[Dict[str, Any]] = None,
    ):
        """Register an MCP tool with its handler function."""
        self._tools[name] = MCPTool(name, description, handler, input_schema)
        logger.info(f"Registered tool: {name}")

    def tool(
        self,
        name: str = "",
        description: str = "",
        input_schema: Optional[Dict[str, Any]] = None,
    ):
        """Decorator for registering tools."""
        def decorator(func: Callable):
            tool_name = name or func.__name__
            tool_desc = description or func.__doc__ or f"Tool: {tool_name}"
            self.register_tool(tool_name, tool_desc, func, input_schema)
            return func
        return decorator

    # ── Main Event Loop ──────────────────────────────────────────────────

    def run(self):
        """
        Enter the stdio message loop.

        Reads JSON-RPC messages from stdin, dispatches them, and writes
        responses to stdout. Runs until stdin is closed (EOF).
        """
        logger.info(f"MCP Server '{self.name}' v{self.version} starting (stdio transport)")

        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    # EOF — client disconnected
                    logger.info("stdin closed, shutting down")
                    break

                line = line.strip()
                if not line:
                    continue

                # Parse the JSON-RPC message
                try:
                    message = json.loads(line)
                except json.JSONDecodeError as e:
                    self._send_error(None, PARSE_ERROR, f"Invalid JSON: {e}")
                    continue

                # Dispatch
                response = self._handle_message(message)
                if response is not None:
                    self._send_response(response)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt, shutting down")
                break
            except Exception as e:
                # Absolute last resort — never crash
                logger.error(f"Unhandled loop error: {e}\n{traceback.format_exc()}")
                try:
                    self._send_error(None, INTERNAL_ERROR, f"Server error: {e}")
                except Exception:
                    pass

        logger.info("Server stopped")

    # ── Message Dispatch ─────────────────────────────────────────────────

    def _handle_message(self, message: dict) -> Optional[dict]:
        """
        Route a JSON-RPC message to the appropriate handler.
        Returns a response dict, or None for notifications.
        """
        try:
            # Validate basic JSON-RPC structure
            if not isinstance(message, dict):
                return self._error_response(None, INVALID_REQUEST, "Message must be a JSON object")

            method = message.get("method")
            msg_id = message.get("id")
            params = message.get("params", {})

            if not method:
                return self._error_response(msg_id, INVALID_REQUEST, "Missing 'method' field")

            # ── MCP Protocol Methods ─────────────────────────────────

            if method == "initialize":
                return self._handle_initialize(msg_id, params)

            elif method == "notifications/initialized":
                # This is a notification (no id) — no response needed
                self._initialized = True
                logger.info("Client confirmed initialization")
                return None

            elif method == "ping":
                return self._success_response(msg_id, {})

            elif method == "tools/list":
                return self._handle_tools_list(msg_id)

            elif method == "tools/call":
                return self._handle_tools_call(msg_id, params)

            else:
                return self._error_response(msg_id, METHOD_NOT_FOUND, f"Unknown method: {method}")

        except Exception as e:
            logger.error(f"Message handling error: {e}\n{traceback.format_exc()}")
            return self._error_response(
                message.get("id") if isinstance(message, dict) else None,
                INTERNAL_ERROR,
                f"Internal server error: {e}",
            )

    # ── MCP Protocol Handlers ────────────────────────────────────────────

    def _handle_initialize(self, msg_id: Any, params: dict) -> dict:
        """Handle the MCP initialize handshake."""
        try:
            return self._success_response(msg_id, {
                "protocolVersion": self.PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": self.name,
                    "version": self.version,
                },
            })
        except Exception as e:
            return self._error_response(msg_id, INTERNAL_ERROR, f"Initialize failed: {e}")

    def _handle_tools_list(self, msg_id: Any) -> dict:
        """Return the list of available tools."""
        try:
            tools = [tool.to_mcp_format() for tool in self._tools.values()]
            return self._success_response(msg_id, {"tools": tools})
        except Exception as e:
            return self._error_response(msg_id, INTERNAL_ERROR, f"Tool listing failed: {e}")

    def _handle_tools_call(self, msg_id: Any, params: dict) -> dict:
        """Execute a tool call and return the result."""
        try:
            tool_name = params.get("name")
            if not tool_name:
                return self._error_response(msg_id, INVALID_PARAMS, "Missing tool 'name' in params")

            tool = self._tools.get(tool_name)
            if not tool:
                available = ", ".join(self._tools.keys())
                return self._error_response(
                    msg_id, METHOD_NOT_FOUND,
                    f"Tool '{tool_name}' not found. Available: {available}"
                )

            # Extract tool arguments
            arguments = params.get("arguments", {})
            if not isinstance(arguments, dict):
                arguments = {}

            # Call the tool handler with comprehensive error catching
            try:
                result = tool.handler(**arguments)
            except TypeError as e:
                # Wrong arguments — give a helpful message
                return self._error_response(
                    msg_id, INVALID_PARAMS,
                    f"Invalid arguments for tool '{tool_name}': {e}"
                )
            except Exception as e:
                logger.error(f"Tool '{tool_name}' execution error: {e}\n{traceback.format_exc()}")
                # Return error as content (not a JSON-RPC error) so the AI can see it
                return self._success_response(msg_id, {
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "error": True,
                            "tool": tool_name,
                            "message": str(e),
                            "type": type(e).__name__,
                        }, indent=2, default=str),
                    }],
                    "isError": True,
                })

            # Serialize the result
            try:
                result_text = json.dumps(result, indent=2, default=str, ensure_ascii=False)
            except (TypeError, ValueError) as e:
                result_text = json.dumps({"result": str(result)}, indent=2)

            return self._success_response(msg_id, {
                "content": [{
                    "type": "text",
                    "text": result_text,
                }],
            })

        except Exception as e:
            logger.error(f"Tool call dispatch error: {e}\n{traceback.format_exc()}")
            return self._error_response(msg_id, INTERNAL_ERROR, f"Tool call failed: {e}")

    # ── Response Builders ────────────────────────────────────────────────

    def _success_response(self, msg_id: Any, result: Any) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": result,
        }

    def _error_response(self, msg_id: Any, code: int, message: str, data: Any = None) -> dict:
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": error,
        }

    # ── IO ────────────────────────────────────────────────────────────────

    def _send_response(self, response: dict):
        """Write a JSON-RPC response to stdout."""
        try:
            line = json.dumps(response, default=str, ensure_ascii=False)
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    def _send_error(self, msg_id: Any, code: int, message: str):
        """Convenience: build and send an error response."""
        self._send_response(self._error_response(msg_id, code, message))
