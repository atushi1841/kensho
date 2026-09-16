"""
MCP Hazard Server — Model Context Protocol サーバー実装
OpenAI互換MCPプロトコルでハザードデータを提供
"""

import json
import logging
from typing import Any

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field

from mcp_hazard.hazard import get_hazard, HazardResult

logger = logging.getLogger(__name__)

app = FastAPI(title="MCP Hazard Server", version="0.1.0")


# ── MCPリクエスト/レスポンススキーマ ──
class HazardRequest(BaseModel):
    address: str = Field(..., description="住所")
    lat: float = Field(..., ge=-90, le=90, description="緯度")
    lon: float = Field(..., ge=-180, le=180, description="経度")


class HazardResponse(BaseModel):
    address: str
    lat: float
    lon: float
    flood: int
    landslide: int
    tsunami: int
    liquefaction: int
    sources: list


# ── MCPツール定義 ──
TOOLS = [
    {
        "name": "get_hazard",
        "description": "指定住所のハザードリスクレベルを取得 (flood, landslide, tsunami, liquefaction 各0-3)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "住所"},
                "lat": {"type": "number", "description": "緯度"},
                "lon": {"type": "number", "description": "経度"},
            },
            "required": ["address", "lat", "lon"],
        },
    }
]


@app.get("/mcp")
async def mcp_root():
    """MCP接続確認エンドポイント"""
    return {"status": "ok", "tools": [t["name"] for t in TOOLS]}


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCPプロトコルメインエンドポイント"""
    body = await request.json()
    method = body.get("method")
    params = body.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "result": {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mcp-hazard", "version": "0.1.0"},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name != "get_hazard":
            raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")

        result = get_hazard(
            address=arguments.get("address", ""),
            lat=arguments.get("lat", 0.0),
            lon=arguments.get("lon", 0.0),
        )

        return {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "result": {
                "content": [{"type": "text", "text": json.dumps(result.to_dict())}],
            },
        }

    raise HTTPException(status_code=400, detail=f"Unknown method: {method}")


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)