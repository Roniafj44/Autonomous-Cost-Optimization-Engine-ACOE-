"""
ACOE — MCP Server Launcher
============================
Unified launcher for all ACOE MCP servers.

Usage:
  python mcp_servers/launcher.py                     # List all servers
  python mcp_servers/launcher.py pipeline            # Start pipeline server
  python mcp_servers/launcher.py data                # Start data server
  python mcp_servers/launcher.py config              # Start config server
  python mcp_servers/launcher.py monitoring          # Start monitoring server
  python mcp_servers/launcher.py --test              # Run self-tests on all servers
  python mcp_servers/launcher.py pipeline --test     # Test pipeline server only

All servers use stdio transport (JSON-RPC 2.0 over stdin/stdout).
"""

from __future__ import annotations

import io
import json
import os
import sys
import traceback

# Fix Windows console encoding (prevents UnicodeEncodeError on cp1252)
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# ── Ensure ACOE root is importable ──────────────────────────────────────────
ACOE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ACOE_ROOT not in sys.path:
    sys.path.insert(0, ACOE_ROOT)

# Server registry
SERVERS = {
    "pipeline": {
        "module": "mcp_servers.pipeline_server",
        "attr": "server",
        "description": "7-stage autonomous cost optimization pipeline (8 tools)",
    },
    "data": {
        "module": "mcp_servers.data_server",
        "attr": "server",
        "description": "CRUD operations on enterprise data sources (5 tools)",
    },
    "config": {
        "module": "mcp_servers.config_server",
        "attr": "server",
        "description": "Dynamic configuration management (4 tools)",
    },
    "monitoring": {
        "module": "mcp_servers.monitoring_server",
        "attr": "server",
        "description": "System monitoring and analytics (6 tools)",
    },
}


def list_servers():
    """Print available servers."""
    print("\n==============================================================")
    print("   ACOE -- MCP Server Launcher")
    print("==============================================================\n")
    print("Available MCP Servers:\n")
    for name, info in SERVERS.items():
        print(f"  {name:15s}  {info['description']}")
    print()
    print("Usage:")
    print("  python mcp_servers/launcher.py <server_name>")
    print("  python mcp_servers/launcher.py <server_name> --test")
    print("  python mcp_servers/launcher.py --test   (test all)")
    print()


def load_server(name: str):
    """Dynamically import and return a server instance."""
    info = SERVERS.get(name)
    if not info:
        print(f"Error: Unknown server '{name}'")
        print(f"Available: {', '.join(SERVERS.keys())}")
        sys.exit(1)

    try:
        import importlib
        module = importlib.import_module(info["module"])
        server = getattr(module, info["attr"])
        return server
    except Exception as e:
        print(f"Error loading server '{name}': {e}")
        traceback.print_exc()
        sys.exit(1)


def test_server(name: str, server) -> bool:
    """Run self-tests on a server."""
    print(f"\n-- Testing: {name} ----------------------------------------")

    errors = []

    # Test 1: Initialize handshake
    try:
        response = server._handle_message({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        })
        assert response is not None, "No response from initialize"
        assert "result" in response, f"Error in initialize: {response.get('error')}"
        print(f"  ✅ Initialize handshake OK")
    except Exception as e:
        errors.append(f"Initialize: {e}")
        print(f"  ❌ Initialize handshake FAILED: {e}")

    # Test 2: List tools
    try:
        response = server._handle_message({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
        })
        assert response is not None
        assert "result" in response, f"Error in tools/list: {response.get('error')}"
        tools = response["result"]["tools"]
        print(f"  ✅ Tools listed: {len(tools)} tools")
        for tool in tools:
            print(f"     • {tool['name']}: {tool['description'][:60]}...")
    except Exception as e:
        errors.append(f"Tools list: {e}")
        print(f"  ❌ Tools list FAILED: {e}")

    # Test 3: Call each tool with default/empty args
    try:
        tools = response["result"]["tools"]
        for tool in tools:
            tool_name = tool["name"]
            try:
                call_response = server._handle_message({
                    "jsonrpc": "2.0",
                    "id": 100,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": {},
                    },
                })
                assert call_response is not None
                if "error" in call_response:
                    print(f"     ⚠️  {tool_name}: JSON-RPC error: {call_response['error']['message']}")
                else:
                    content = call_response.get("result", {}).get("content", [{}])
                    is_error = call_response.get("result", {}).get("isError", False)
                    if is_error:
                        text = content[0].get("text", "") if content else ""
                        print(f"     ⚠️  {tool_name}: Tool returned error (handled gracefully)")
                    else:
                        text = content[0].get("text", "") if content else ""
                        try:
                            data = json.loads(text)
                            success = data.get("success", "unknown")
                            print(f"     ✅ {tool_name}: success={success}")
                        except Exception:
                            print(f"     ✅ {tool_name}: returned response")
            except Exception as e:
                print(f"     ❌ {tool_name}: {e}")
                errors.append(f"Tool {tool_name}: {e}")
    except Exception as e:
        errors.append(f"Tool calls: {e}")
        print(f"  ❌ Tool calls FAILED: {e}")

    # Test 4: Unknown method (should return error, not crash)
    try:
        response = server._handle_message({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "nonexistent/method",
        })
        assert response is not None
        assert "error" in response, "Expected error for unknown method"
        print(f"  ✅ Unknown method handling OK")
    except Exception as e:
        errors.append(f"Error handling: {e}")
        print(f"  ❌ Error handling FAILED: {e}")

    # Test 5: Malformed request (should not crash)
    try:
        response = server._handle_message({"invalid": True})
        assert response is not None
        print(f"  ✅ Malformed request handling OK")
    except Exception as e:
        errors.append(f"Malformed handling: {e}")
        print(f"  ❌ Malformed request FAILED: {e}")

    # Test 6: Ping
    try:
        response = server._handle_message({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "ping",
        })
        assert response is not None
        assert "result" in response
        print(f"  ✅ Ping OK")
    except Exception as e:
        errors.append(f"Ping: {e}")
        print(f"  ❌ Ping FAILED: {e}")

    if errors:
        print(f"\n  ❌ {len(errors)} test(s) failed for {name}")
        return False
    else:
        print(f"\n  ✅ All tests passed for {name}")
        return True


def main():
    args = sys.argv[1:]

    if not args:
        list_servers()
        return

    run_tests = "--test" in args
    server_name = None

    for arg in args:
        if arg != "--test" and arg in SERVERS:
            server_name = arg
            break

    if run_tests:
        # Run tests
        if server_name:
            # Test specific server
            srv = load_server(server_name)
            passed = test_server(server_name, srv)
            sys.exit(0 if passed else 1)
        else:
            # Test all servers
            print("\n==============================================================")
            print("   ACOE MCP Server Self-Test Suite")
            print("==============================================================")

            all_passed = True
            for name in SERVERS:
                try:
                    srv = load_server(name)
                    passed = test_server(name, srv)
                    if not passed:
                        all_passed = False
                except Exception as e:
                    print(f"\n  ❌ {name}: Failed to load: {e}")
                    all_passed = False

            print("\n" + "=" * 60)
            if all_passed:
                print("✅ ALL SERVERS PASSED SELF-TESTS")
            else:
                print("❌ SOME TESTS FAILED — see details above")
            print("=" * 60)
            sys.exit(0 if all_passed else 1)

    elif server_name:
        # Start server
        srv = load_server(server_name)
        print(f"Starting ACOE MCP Server: {server_name}", file=sys.stderr)
        srv.run()

    else:
        unknown = [a for a in args if a != "--test"]
        if unknown:
            print(f"Error: Unknown argument(s): {unknown}")
            print(f"Available servers: {', '.join(SERVERS.keys())}")
        else:
            list_servers()


if __name__ == "__main__":
    main()
