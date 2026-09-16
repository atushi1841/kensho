"""
MCP Hazard Server — Model Context Protocol サーバー
日本物件ハザードリスク (洪水/土砂/津波/液状化) を住所から返す。

エンドポイント:
  GET  /mcp    接続確認
  POST /mcp    JSON-RPC 2.0 (initialize / tools/list / tools/call)
  GET  /health ヘルスチェック
"""

import json
import uuid
import logging
from typing import Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from mcp_hazard.hazard import get_hazard, geocode_address, CREDIT_TEXT

logger = logging.getLogger(__name__)

app = FastAPI(title="MCP Hazard Server", version="0.2.0")

PROTOCOL_VERSION = "2025-06-18"


# ── MCPリクエスト/レスポンススキーマ ──
class HazardRequest(BaseModel):
    address: str = Field(..., description="住所 (例: 東京都千代田区丸の内1-1)")
    lat: float | None = Field(None, ge=-90, le=90, description="緯度(省略可)")
    lon: float | None = Field(None, ge=-180, le=180, description="経度(省略可)")


# ── MCPツール定義 ──
TOOLS = [
    {
        "name": "get_hazard",
        "description": (
            "指定住所のハザードリスクレベルを返す。"
            "洪水(flood)/土砂(landslide)/津波(tsunami)/液状化(liquefaction) を各0-3で報告。"
            "0=区域外, 1=低, 2=中, 3=高。住所のみで呼び出し可能(内部でジオコーディング)。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "住所 (例: 東京都千代田区丸の内1-1)"},
                "lat": {"type": "number", "description": "緯度(省略時は住所から解決)"},
                "lon": {"type": "number", "description": "経度(省略時は住所から解決)"},
            },
            "required": ["address"],
        },
    }
]


def _mcp_response(req_id: Any, result: Any, session_id: str | None = None) -> JSONResponse:
    resp = JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})
    if session_id:
        resp.headers["mcp-session-id"] = session_id
    return resp


@app.get("/mcp")
async def mcp_root() -> dict[str, Any]:
    """MCP接続確認エンドポイント"""
    return {"status": "ok", "name": "mcp-hazard", "tools": [t["name"] for t in TOOLS]}


@app.post("/mcp")
async def mcp_endpoint(request: Request) -> Any:
    """MCPプロトコルメインエンドポイント (JSON-RPC 2.0)"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    method = body.get("method")
    params = body.get("params", {}) or {}
    req_id = body.get("id")

    if method == "initialize":
        session_id = str(uuid.uuid4())
        return _mcp_response(
            req_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mcp-hazard", "version": "0.2.0"},
            },
            session_id=session_id,
        )

    if method in ("notifications/initialized", "initialized"):
        return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {}})

    if method == "tools/list":
        return _mcp_response(req_id, {"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {}) or {}
        if tool_name != "get_hazard":
            raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")

        address = arguments.get("address", "")
        lat = arguments.get("lat")
        lon = arguments.get("lon")
        if lat is None or lon is None:
            if not address:
                raise HTTPException(status_code=400, detail="address or lat/lon required")
            try:
                lat, lon, _ = geocode_address(address)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        result = get_hazard(address=address, lat=lat, lon=lon)
        payload = result.to_dict()
        payload["credit"] = CREDIT_TEXT
        return _mcp_response(
            req_id,
            {
                "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                "structuredContent": payload,
            },
        )

    if method == "ping":
        return _mcp_response(req_id, {})

    raise HTTPException(status_code=400, detail=f"Unknown method: {method}")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
