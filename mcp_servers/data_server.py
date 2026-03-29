"""
ACOE — Data Management MCP Server
===================================
CRUD operations on CSV data sources used by the ACOE pipeline.

Tools:
  - data_list_sources:   List all data files with record counts
  - data_read_source:    Read records from a specific data source
  - data_add_record:     Add a new record to a CSV data source
  - data_update_record:  Update an existing record by ID
  - data_get_summary:    Get aggregate statistics across all sources

Usage:
  python mcp_servers/data_server.py
"""

from __future__ import annotations

import csv
import os
import sys
import logging
import traceback
from datetime import datetime
from typing import Optional

# ── Ensure ACOE root is importable ──────────────────────────────────────────
ACOE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ACOE_ROOT not in sys.path:
    sys.path.insert(0, ACOE_ROOT)

from mcp_servers.base import MCPBaseServer
from mcp_servers.utils import safe_read_csv, safe_write_csv, validate_source_name, format_inr

logger = logging.getLogger("acoe.mcp.data")

# Data directory
DATA_DIR = os.path.join(ACOE_ROOT, "data")

# Source file mappings
SOURCE_FILES = {
    "procurement": "procurement.csv",
    "saas_subscriptions": "saas_subscriptions.csv",
    "cloud_usage": "cloud_usage.csv",
    "sla_metrics": "sla_metrics.csv",
}

# ID column for each source
SOURCE_ID_COLUMNS = {
    "procurement": "record_id",
    "saas_subscriptions": "subscription_id",
    "cloud_usage": "resource_id",
    "sla_metrics": "sla_id",
}

# Expected fieldnames for each source
SOURCE_FIELDS = {
    "procurement": [
        "record_id", "vendor_name", "service_category", "contract_value_inr",
        "contract_start", "contract_end", "department", "payment_frequency", "description",
    ],
    "saas_subscriptions": [
        "subscription_id", "vendor_name", "product_name", "total_licenses",
        "active_users", "monthly_cost_inr", "plan_tier", "renewal_date", "department",
    ],
    "cloud_usage": [
        "resource_id", "provider", "resource_type", "region", "capacity_units",
        "avg_usage_units", "peak_usage_units", "monthly_cost_inr", "department",
    ],
    "sla_metrics": [
        "sla_id", "service_name", "vendor_name", "metric_name", "target_value",
        "current_value", "measurement_unit", "breach_penalty_inr",
        "measurement_timestamp", "breach_deadline",
    ],
}


def _get_source_path(source: str) -> str:
    """Get the full file path for a source name."""
    canonical = validate_source_name(source)
    filename = SOURCE_FILES.get(canonical)
    if not filename:
        raise ValueError(f"No file mapped for source '{canonical}'")
    return os.path.join(DATA_DIR, filename)


# ── Create the MCP Server ───────────────────────────────────────────────────

server = MCPBaseServer(
    name="acoe-data",
    version="1.0.0",
    description="ACOE Data Management — CRUD operations on enterprise data sources",
)


# ── Tool: data_list_sources ─────────────────────────────────────────────────

@server.tool(
    name="data_list_sources",
    description=(
        "List all available data sources with file paths, record counts, "
        "and column information. Returns metadata about each CSV file."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
)
def data_list_sources() -> dict:
    """List all data sources with metadata."""
    try:
        sources = []
        for source_name, filename in SOURCE_FILES.items():
            path = os.path.join(DATA_DIR, filename)
            exists = os.path.exists(path)
            rows = safe_read_csv(path) if exists else []

            sources.append({
                "name": source_name,
                "file": filename,
                "path": path,
                "exists": exists,
                "record_count": len(rows),
                "id_column": SOURCE_ID_COLUMNS.get(source_name, ""),
                "columns": SOURCE_FIELDS.get(source_name, []),
            })

        total_records = sum(s["record_count"] for s in sources)

        return {
            "success": True,
            "total_sources": len(sources),
            "total_records": total_records,
            "data_directory": DATA_DIR,
            "sources": sources,
        }
    except Exception as e:
        logger.error(f"List sources failed: {e}\n{traceback.format_exc()}")
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


# ── Tool: data_read_source ──────────────────────────────────────────────────

@server.tool(
    name="data_read_source",
    description=(
        "Read records from a specific data source. "
        "Source can be: procurement, saas, cloud, sla. "
        "Optionally filter by a specific record ID."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Data source name: procurement, saas, cloud, or sla",
            },
            "record_id": {
                "type": "string",
                "description": "Optional: filter to a specific record by its ID",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of records to return (default: 100)",
                "default": 100,
            },
        },
        "required": ["source"],
        "additionalProperties": False,
    },
)
def data_read_source(source: str, record_id: str = "", limit: int = 100) -> dict:
    """Read records from a data source."""
    try:
        canonical = validate_source_name(source)
        path = _get_source_path(source)

        if not os.path.exists(path):
            return {
                "success": False,
                "error": f"Data file not found: {path}",
                "hint": "Place your CSV data files in the data/ directory",
            }

        rows = safe_read_csv(path)
        id_col = SOURCE_ID_COLUMNS.get(canonical, "")

        # Filter by record ID if specified
        if record_id and id_col:
            rows = [r for r in rows if r.get(id_col, "") == record_id]

        # Apply limit
        total = len(rows)
        rows = rows[:limit]

        return {
            "success": True,
            "source": canonical,
            "total_records": total,
            "returned_records": len(rows),
            "id_column": id_col,
            "records": rows,
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Read source failed: {e}\n{traceback.format_exc()}")
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


# ── Tool: data_add_record ───────────────────────────────────────────────────

@server.tool(
    name="data_add_record",
    description=(
        "Add a new record to a data source CSV file. "
        "Provide the source name and a record object with the required fields. "
        "The record will be appended to the CSV file."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Data source: procurement, saas, cloud, or sla",
            },
            "record": {
                "type": "object",
                "description": "Record data as key-value pairs matching the CSV columns",
            },
        },
        "required": ["source", "record"],
        "additionalProperties": False,
    },
)
def data_add_record(source: str, record: dict) -> dict:
    """Add a new record to a data source."""
    try:
        canonical = validate_source_name(source)
        path = _get_source_path(source)
        fieldnames = SOURCE_FIELDS.get(canonical, [])
        id_col = SOURCE_ID_COLUMNS.get(canonical, "")

        if not fieldnames:
            return {"success": False, "error": f"No schema defined for source '{canonical}'"}

        # Validate that the record has at least the ID field
        if id_col and id_col not in record:
            return {
                "success": False,
                "error": f"Record must include '{id_col}' field",
                "required_fields": fieldnames,
            }

        # Check for duplicate ID
        existing = safe_read_csv(path)
        if id_col and any(r.get(id_col) == record.get(id_col) for r in existing):
            return {
                "success": False,
                "error": f"Record with {id_col}='{record[id_col]}' already exists",
                "hint": "Use data_update_record to modify existing records",
            }

        # Fill missing optional fields with empty strings
        clean_record = {}
        for field in fieldnames:
            clean_record[field] = str(record.get(field, ""))

        # Append to CSV
        existing.append(clean_record)
        success = safe_write_csv(path, existing, fieldnames)

        if success:
            return {
                "success": True,
                "source": canonical,
                "record_id": record.get(id_col, ""),
                "total_records": len(existing),
                "message": f"Record added to {canonical} ({len(existing)} total records)",
            }
        else:
            return {"success": False, "error": "Failed to write CSV file"}

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Add record failed: {e}\n{traceback.format_exc()}")
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


# ── Tool: data_update_record ────────────────────────────────────────────────

@server.tool(
    name="data_update_record",
    description=(
        "Update an existing record in a data source by its ID. "
        "Only the fields you provide will be updated; others remain unchanged."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Data source: procurement, saas, cloud, or sla",
            },
            "record_id": {
                "type": "string",
                "description": "The ID of the record to update",
            },
            "updates": {
                "type": "object",
                "description": "Fields to update as key-value pairs",
            },
        },
        "required": ["source", "record_id", "updates"],
        "additionalProperties": False,
    },
)
def data_update_record(source: str, record_id: str, updates: dict) -> dict:
    """Update an existing record."""
    try:
        canonical = validate_source_name(source)
        path = _get_source_path(source)
        fieldnames = SOURCE_FIELDS.get(canonical, [])
        id_col = SOURCE_ID_COLUMNS.get(canonical, "")

        if not os.path.exists(path):
            return {"success": False, "error": f"Data file not found: {path}"}

        rows = safe_read_csv(path)
        found = False

        for row in rows:
            if row.get(id_col) == record_id:
                for key, value in updates.items():
                    if key in fieldnames:
                        row[key] = str(value)
                    else:
                        logger.warning(f"Ignoring unknown field '{key}' for {canonical}")
                found = True
                break

        if not found:
            return {
                "success": False,
                "error": f"Record '{record_id}' not found in {canonical}",
                "hint": f"Use data_read_source to list available records",
            }

        success = safe_write_csv(path, rows, fieldnames)

        if success:
            return {
                "success": True,
                "source": canonical,
                "record_id": record_id,
                "fields_updated": list(updates.keys()),
                "message": f"Record '{record_id}' updated in {canonical}",
            }
        else:
            return {"success": False, "error": "Failed to write CSV file"}

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Update record failed: {e}\n{traceback.format_exc()}")
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


# ── Tool: data_get_summary ──────────────────────────────────────────────────

@server.tool(
    name="data_get_summary",
    description=(
        "Get aggregate statistics across all data sources. "
        "Includes total spend, record counts by source, "
        "and key financial metrics."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
)
def data_get_summary() -> dict:
    """Get aggregate data summary."""
    try:
        summary = {
            "total_records": 0,
            "sources": {},
        }

        # Procurement summary
        proc_rows = safe_read_csv(os.path.join(DATA_DIR, "procurement.csv"))
        proc_total = 0.0
        for row in proc_rows:
            try:
                proc_total += float(row.get("contract_value_inr", 0))
            except (ValueError, TypeError):
                pass
        summary["sources"]["procurement"] = {
            "records": len(proc_rows),
            "total_contract_value_inr": round(proc_total, 2),
            "total_contract_value_formatted": format_inr(proc_total),
        }
        summary["total_records"] += len(proc_rows)

        # SaaS summary
        saas_rows = safe_read_csv(os.path.join(DATA_DIR, "saas_subscriptions.csv"))
        saas_monthly = 0.0
        total_licenses = 0
        active_users = 0
        for row in saas_rows:
            try:
                saas_monthly += float(row.get("monthly_cost_inr", 0))
                total_licenses += int(row.get("total_licenses", 0))
                active_users += int(row.get("active_users", 0))
            except (ValueError, TypeError):
                pass
        avg_utilization = (active_users / total_licenses * 100) if total_licenses > 0 else 0
        summary["sources"]["saas_subscriptions"] = {
            "records": len(saas_rows),
            "monthly_cost_inr": round(saas_monthly, 2),
            "monthly_cost_formatted": format_inr(saas_monthly),
            "annual_cost_inr": round(saas_monthly * 12, 2),
            "annual_cost_formatted": format_inr(saas_monthly * 12),
            "total_licenses": total_licenses,
            "active_users": active_users,
            "avg_utilization_pct": round(avg_utilization, 1),
        }
        summary["total_records"] += len(saas_rows)

        # Cloud summary
        cloud_rows = safe_read_csv(os.path.join(DATA_DIR, "cloud_usage.csv"))
        cloud_monthly = 0.0
        for row in cloud_rows:
            try:
                cloud_monthly += float(row.get("monthly_cost_inr", 0))
            except (ValueError, TypeError):
                pass
        summary["sources"]["cloud_usage"] = {
            "records": len(cloud_rows),
            "monthly_cost_inr": round(cloud_monthly, 2),
            "monthly_cost_formatted": format_inr(cloud_monthly),
            "annual_cost_inr": round(cloud_monthly * 12, 2),
            "annual_cost_formatted": format_inr(cloud_monthly * 12),
        }
        summary["total_records"] += len(cloud_rows)

        # SLA summary
        sla_rows = safe_read_csv(os.path.join(DATA_DIR, "sla_metrics.csv"))
        total_penalty_risk = 0.0
        for row in sla_rows:
            try:
                total_penalty_risk += float(row.get("breach_penalty_inr", 0))
            except (ValueError, TypeError):
                pass
        summary["sources"]["sla_metrics"] = {
            "records": len(sla_rows),
            "total_penalty_risk_inr": round(total_penalty_risk, 2),
            "total_penalty_risk_formatted": format_inr(total_penalty_risk),
        }
        summary["total_records"] += len(sla_rows)

        # Grand totals
        total_monthly = saas_monthly + cloud_monthly + (proc_total / 12)
        summary["grand_totals"] = {
            "total_monthly_spend_inr": round(total_monthly, 2),
            "total_monthly_spend_formatted": format_inr(total_monthly),
            "total_annual_spend_inr": round(total_monthly * 12, 2),
            "total_annual_spend_formatted": format_inr(total_monthly * 12),
            "total_penalty_exposure_inr": round(total_penalty_risk, 2),
        }

        return {"success": True, **summary}

    except Exception as e:
        logger.error(f"Data summary failed: {e}\n{traceback.format_exc()}")
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    server.run()
