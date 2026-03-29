"""
ACOE — MCP Shared Utilities
============================
Serialization helpers, error formatting, and safe wrappers used
by all MCP servers. Every function is defensively coded to never raise.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from datetime import datetime
from typing import Any

logger = logging.getLogger("acoe.mcp.utils")

# ── Ensure ACOE root is on sys.path ─────────────────────────────────────────

ACOE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ACOE_ROOT not in sys.path:
    sys.path.insert(0, ACOE_ROOT)


def safe_serialize(obj: Any) -> Any:
    """
    Safely convert any object to a JSON-serializable form.
    Never raises — worst case returns a string representation.
    """
    try:
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, (list, tuple)):
            return [safe_serialize(item) for item in obj]
        if isinstance(obj, dict):
            return {str(k): safe_serialize(v) for k, v in obj.items()}
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "model_dump"):
            # Pydantic v2
            try:
                return obj.model_dump(mode="json")
            except Exception:
                return obj.model_dump()
        if hasattr(obj, "dict"):
            # Pydantic v1
            return obj.dict()
        if hasattr(obj, "__dict__"):
            return {k: safe_serialize(v) for k, v in obj.__dict__.items()
                    if not k.startswith("_")}
        # Fallback
        return str(obj)
    except Exception as e:
        logger.warning(f"Serialization fallback for {type(obj).__name__}: {e}")
        return str(obj)


def safe_call(func, *args, error_msg: str = "Operation failed", **kwargs) -> dict:
    """
    Call a function safely, returning a standardized result dict.
    Never raises — wraps all exceptions into an error response.
    """
    try:
        result = func(*args, **kwargs)
        return {
            "success": True,
            "data": safe_serialize(result),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"{error_msg}: {e}\n{traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "message": error_msg,
            "timestamp": datetime.utcnow().isoformat(),
        }


def format_inr(amount: float) -> str:
    """Format a number as INR currency string. Never raises."""
    try:
        if amount < 0:
            return f"-₹{abs(amount):,.0f}"
        return f"₹{amount:,.0f}"
    except Exception:
        return f"₹{amount}"


def safe_read_csv(path: str) -> list:
    """Read a CSV file safely, returning a list of dicts. Never raises."""
    import csv
    try:
        if not os.path.exists(path):
            logger.warning(f"CSV file not found: {path}")
            return []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception as e:
        logger.error(f"Failed to read CSV {path}: {e}")
        return []


def safe_write_csv(path: str, rows: list, fieldnames: list) -> bool:
    """Write rows to a CSV file safely. Never raises."""
    import csv
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return True
    except Exception as e:
        logger.error(f"Failed to write CSV {path}: {e}")
        return False


def validate_source_name(source: str) -> str:
    """
    Validate and normalize a data source name.
    Returns the canonical name or raises ValueError.
    """
    mapping = {
        "procurement": "procurement",
        "saas": "saas_subscriptions",
        "saas_subscriptions": "saas_subscriptions",
        "cloud": "cloud_usage",
        "cloud_usage": "cloud_usage",
        "sla": "sla_metrics",
        "sla_metrics": "sla_metrics",
    }
    normalized = source.lower().strip()
    if normalized in mapping:
        return mapping[normalized]
    valid = list(mapping.keys())
    raise ValueError(
        f"Invalid source '{source}'. Valid sources: {valid}"
    )
