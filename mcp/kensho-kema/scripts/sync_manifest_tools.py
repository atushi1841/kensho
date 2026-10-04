"""稼働中MCPサーバーのツール情報を引き出して manifest.json の tools 配列を同期する。

Smitheryのstdio公開APIは各ツールに inputSchema を要求する（欠けると400）
FastMCP 4.x では _list_tools() がコルーチンを返し、FunctionTool.parameters に JSON Schema が含まれる。
stdio接続を使わず直接引き出す方式（uv run がstdin待ちでhangする問題を回避）。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

BUNDLE_DIR = sys.argv[1] if len(sys.argv) > 1 else "/mnt/d/Project2/kensho/mcp/kensho-kema"
MANIFEST = os.path.join(BUNDLE_DIR, "manifest.json")


def fetch_tools() -> list[dict]:
    sys.path.insert(0, BUNDLE_DIR)
    from server.server import server

    raw = asyncio.run(server._list_tools())
    out: list[dict] = []
    for t in raw:
        entry: dict[str, object] = {"name": t.name}
        if t.description:
            entry["description"] = t.description
        schema = getattr(t, "parameters", None)
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        entry["inputSchema"] = schema
        out.append(entry)
    return out


def main() -> None:
    tools = fetch_tools()
    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    manifest["tools"] = tools
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"tools同期: {len(tools)}件 -> {MANIFEST}")
    for t in tools:
        print(" -", t["name"], "| schema keys:", list(t["inputSchema"].get("properties", {})))


if __name__ == "__main__":
    main()