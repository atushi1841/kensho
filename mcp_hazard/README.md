# MCP Hazard Server — 日本物件ハザードリスク

住所を渡すと、その地点のハザードリスク(洪水・土砂・津波・液状化)を 0-3 で返す
Model Context Protocol サーバー。AIエージェント(Claude / ChatGPT / Cursor 等)から
ツールとして呼び出せる。

## アーキテクチャ

```
住所文字列
  │  (1) ジオコーディング: 国土地理院 住所検索API (APIキー不要)
  ▼
緯度経度 (lat, lon)
  │  (2) ハザード取得: 国土交通省 不動産情報ライブラリAPI (XKT025-029, BYOK)
  ▼
{address, lat, lon, flood, landslide, tsunami, liquefaction, sources, credit}
```

## リスクレベル定義 (0-3)

| レベル | 意味 |
|--------|------|
| 0 | 情報なし / 区域外 |
| 1 | 低 (浸水深 <0.5m 等) |
| 2 | 中 (浸水深 0.5〜3m) |
| 3 | 高 (浸水深 >=3m / 警戒区域内) |

## 出力例

```json
{
  "address": "東京都千代田区丸の内1-1",
  "lat": 35.684559,
  "lon": 139.761765,
  "flood": 0, "landslide": 0, "tsunami": 0, "liquefaction": 0,
  "sources": ["MLIT_XKT025","MLIT_XKT026","MLIT_XKT027","MLIT_XKT028","MLIT_XKT029"],
  "credit": "出典: 国土交通省 不動産情報ライブラリAPI (国土数値情報, CC-BY 4.0相当) ..."
}
```

## セットアップ

```bash
export MLIT_API_KEY="<あなたのAPIキー>"   # BYOK: 利用者自身が取得
```

### MLIT 不動産情報ライブラリAPIキーの取得 (無料)

1. https://www.reinfolib.mlit.go.jp/ にアクセス
2. 「API利用申請」からメールアドレス等を登録
3. 発行されたキーを `Ocp-Apim-Subscription-Key` として設定
   (`MLIT_API_KEY` 環境変数、または `get_hazard(api_key=...)` 引数)

キー未設定の場合、ジオコーディングは動作するがハザード値は全て 0(情報なし)となる。

## ローカル実行

```bash
uvicorn mcp_hazard.server:app --host 0.0.0.0 --port 8000
# または
python mcp_hazard/server.py
```

## MCP 接続確認

```bash
BASE=http://localhost:8000

# initialize
curl -sS -D /tmp/h.txt -X POST $BASE/mcp \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"t","version":"1.0"}}}'

# tools/list
curl -sS -X POST $BASE/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# tools/call (住所のみ)
curl -sS -X POST $BASE/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_hazard","arguments":{"address":"東京都千代田区丸の内1-1"}}}'
```

## テスト

```bash
python -m pytest tests/test_mcp_hazard.py -v   # 26 tests
python -m mypy mcp_hazard/                      # strict 0 error
```

## データソースとライセンス

- ジオコーディング: 国土地理院 住所検索API (キー不要)
- ハザード: 国土交通省 不動産情報ライブラリAPI (XKT025-029)
- 出典表示は出力の `credit` フィールドに必ず含まれる (CC-BY 4.0相当)

## Apify Actor

- `actor.json`: `usesStandbyMode: true`, `webServerMcpPath: "/mcp"`
- `pay_per_event.json`: `$0.005/call` (PPE課金)
