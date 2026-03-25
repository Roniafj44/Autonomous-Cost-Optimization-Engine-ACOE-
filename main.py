"""
ACOE -- Main Entry Point
Launches the autonomous daemon via ProcessManager.
For legacy compat, can also run the basic orchestrator directly.
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Use process_manager for full v2 functionality
from process_manager import main

if __name__ == "__main__":
    asyncio.run(main())
