"""Entry point for AT Bridge MCP server."""

import asyncio

from src.at_bridge.server import main

if __name__ == "__main__":
    asyncio.run(main())
