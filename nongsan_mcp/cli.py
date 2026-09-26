#!/usr/bin/env python3
"""CLI entry point for nongsan-mcp."""

import sys
from nongsan_mcp.nongsan_mcp import (
    mcp,
    build_data_from_excel,
)

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  nongsan-mcp --build     # Build data cache from Excel")
        print("  nongsan-mcp --serve     # Run MCP stdio server")
        print("  nongsan-mcp --http      # Run MCP HTTP server")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "--build":
        build_data_from_excel()
    elif cmd == "--serve":
        mcp.run(transport="stdio")
    elif cmd == "--http":
        mcp.run(transport="streamable-http")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()