"""
ACOE — Configuration MCP Server
=================================
Dynamic configuration management for the ACOE engine.

Tools:
  - config_get_all:    Get the complete current configuration
  - config_get_value:  Get a specific config value by dot-notation key
  - config_set_value:  Update a specific config value dynamically
  - config_reset:      Reload config from config.yaml

Usage:
  python mcp_servers/config_server.py
"""

from __future__ import annotations

import os
import sys
import logging
import traceback
from datetime import datetime

# ── Ensure ACOE root is importable ──────────────────────────────────────────
ACOE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ACOE_ROOT not in sys.path:
    sys.path.insert(0, ACOE_ROOT)

from mcp_servers.base import MCPBaseServer
from mcp_servers.utils import safe_serialize

logger = logging.getLogger("acoe.mcp.config")


def _get_config():
    """Safely get the ACOE Config singleton."""
    try:
        from config import get_config
        return get_config()
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        raise RuntimeError(f"Config system unavailable: {e}")


# ── Create the MCP Server ───────────────────────────────────────────────────

server = MCPBaseServer(
    name="acoe-config",
    version="1.0.0",
    description="ACOE Configuration Management — read and update engine settings",
)


# ── Tool: config_get_all ────────────────────────────────────────────────────

@server.tool(
    name="config_get_all",
    description=(
        "Get the complete current ACOE configuration as a structured object. "
        "Includes all sections: system, scheduler, thresholds, decision, "
        "execution, safety, circuit_breaker, logging, database, api, prediction."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
)
def config_get_all() -> dict:
    """Get the full configuration."""
    try:
        cfg = _get_config()
        return {
            "success": True,
            "config": safe_serialize(cfg.to_dict()),
            "config_file": os.path.join(ACOE_ROOT, "config.yaml"),
            "sections": list(cfg.to_dict().keys()),
        }
    except Exception as e:
        logger.error(f"Config get_all failed: {e}\n{traceback.format_exc()}")
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


# ── Tool: config_get_value ──────────────────────────────────────────────────

@server.tool(
    name="config_get_value",
    description=(
        "Get a specific configuration value using dot notation. "
        "Examples: 'thresholds.saas_utilization_pct', 'decision.min_confidence', "
        "'scheduler.interval_seconds', 'safety.max_actions_per_cycle'."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "Dot-notation config key (e.g. 'thresholds.saas_utilization_pct')",
            },
        },
        "required": ["key"],
        "additionalProperties": False,
    },
)
def config_get_value(key: str) -> dict:
    """Get a specific config value."""
    try:
        cfg = _get_config()
        value = cfg.get(key)

        if value is None:
            # Try to give helpful suggestions
            all_keys = []
            config_dict = cfg.to_dict()
            for section, values in config_dict.items():
                if isinstance(values, dict):
                    for k in values:
                        all_keys.append(f"{section}.{k}")
                else:
                    all_keys.append(section)

            return {
                "success": False,
                "error": f"Config key '{key}' not found",
                "available_keys": sorted(all_keys),
                "hint": "Use dot notation like 'section.key'",
            }

        return {
            "success": True,
            "key": key,
            "value": safe_serialize(value),
            "type": type(value).__name__,
        }
    except Exception as e:
        logger.error(f"Config get_value failed: {e}\n{traceback.format_exc()}")
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


# ── Tool: config_set_value ──────────────────────────────────────────────────

@server.tool(
    name="config_set_value",
    description=(
        "Update a specific configuration value dynamically. "
        "Changes take effect immediately for subsequent pipeline runs. "
        "NOTE: Changes are in-memory only — restart resets to config.yaml values. "
        "Example: set 'thresholds.saas_utilization_pct' to 30 for less aggressive detection."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "Dot-notation config key to update",
            },
            "value": {
                "description": "New value to set (string, number, or boolean)",
            },
        },
        "required": ["key", "value"],
        "additionalProperties": False,
    },
)
def config_set_value(key: str, value) -> dict:
    """Set a config value dynamically."""
    try:
        cfg = _get_config()

        # Get old value for comparison
        old_value = cfg.get(key)

        # Validate dangerous keys
        protected_keys = [
            "database.type", "database.path",
            "api.host", "api.port",
        ]
        if key in protected_keys:
            return {
                "success": False,
                "error": f"Key '{key}' is protected and cannot be changed at runtime",
                "hint": "Edit config.yaml directly and restart the server",
            }

        # Type coercion for common cases
        if isinstance(old_value, bool) and isinstance(value, str):
            value = value.lower() in ("true", "1", "yes")
        elif isinstance(old_value, int) and isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                pass
        elif isinstance(old_value, float) and isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                pass

        cfg.set(key, value)

        return {
            "success": True,
            "key": key,
            "old_value": safe_serialize(old_value),
            "new_value": safe_serialize(value),
            "message": f"Config '{key}' updated: {old_value} → {value}",
            "note": "Change is in-memory only. Restart resets to config.yaml values.",
        }
    except Exception as e:
        logger.error(f"Config set_value failed: {e}\n{traceback.format_exc()}")
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


# ── Tool: config_reset ──────────────────────────────────────────────────────

@server.tool(
    name="config_reset",
    description=(
        "Reload configuration from config.yaml, discarding any in-memory overrides. "
        "Use this to reset after making dynamic changes."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
)
def config_reset() -> dict:
    """Reset config to yaml file values."""
    try:
        cfg = _get_config()
        cfg.reload()

        return {
            "success": True,
            "message": "Configuration reloaded from config.yaml",
            "config_file": os.path.join(ACOE_ROOT, "config.yaml"),
            "sections": list(cfg.to_dict().keys()),
        }
    except Exception as e:
        logger.error(f"Config reset failed: {e}\n{traceback.format_exc()}")
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    server.run()
