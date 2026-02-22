"""Local development launcher — starts FastAPI and MCP server simultaneously.

Usage:
    python scripts/dev_server.py
    # or
    make dev
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import time


def main() -> None:
    os.environ.setdefault("FAIRFETCH_TEST_MODE", "true")
    os.environ.setdefault("PYTHONPATH", os.getcwd())

    print("=" * 60)
    print("  Fairfetch Local Development Server")
    print("=" * 60)
    print()
    print("  FastAPI  → http://localhost:8402")
    print("  Docs     → http://localhost:8402/docs")
    print("  Health   → http://localhost:8402/health")
    print()
    print("  MCP Server running on stdio (use MCP Inspector to test)")
    print("  Run: npx @modelcontextprotocol/inspector python -m mcp_server.server")
    print()
    print("  Test payment: curl -H 'X-PAYMENT: test_paid_fairfetch' \\")
    print("    'http://localhost:8402/content/fetch?url=https://example.com'")
    print()
    print("=" * 60)
    print()

    api_process = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "api.main:app",
            "--host", "0.0.0.0",
            "--port", "8402",
            "--reload",
        ],
        env={**os.environ},
    )

    def shutdown(signum, frame):
        print("\nShutting down...")
        api_process.terminate()
        api_process.wait(timeout=5)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        api_process.wait()
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
