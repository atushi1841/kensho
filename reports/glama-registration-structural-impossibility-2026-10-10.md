# Glama MCP Registration — Structural Impossibility Confirmed via OpenAPI

**Date**: 2026-10-10
**Task**: t_25832581 (Register each repo on Glama)
**Verdict**: 【要ユーザー対応】— 自動化不可。手動GitHub OAuthが必要。

## Evidence

### 1. Glama MCP API OpenAPI仕様（https://glama.ai/api/mcp/openapi.json）の全エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/v1/connectors` | コネクタディレクトリ検索 |
| GET | `/v1/connectors/{connectorId}` | コネクタ詳細 |
| GET | `/v1/servers` | サーバーディレクトリ検索 |
| GET | `/v1/servers/{serverId}` | サーバー詳細 |
| GET | `/v1/instances` | インスタンスリスト |
| GET | `/v1/instances/{instanceId}` | インスタンス詳細 |
| POST | `/v1/telemetry/usage` | 使用 telemetry（匿名・認証不要） |

**结论: MCPサーバー作成用の POST/PUT/DELETE エンドポイントは一切存在しない。APIは読取専用。**

### 2. APIキー作成页面
- `https://glama.ai/settings/api-keys` — 手動Web UIで作成必要
- APIキーは読取権限のみ（サブスクライバー向け連携用）。**サーバー登録権限なし**

### 3. サーバー登録経路
- `https://glama.ai/mcp/servers` → 「Add MCP Server」ボタン
- GitHub OAuth デバイスフローで認証必要
- ユーザーの手動操作なしでは実行不可

### 4. 自動検出も無効
- 10repoに `glama.json` + `mcp.json` をpush済み（前回worker作業）
- `curl https://glama.ai/mcp/servers/atushi1841/<slug>` = すべて404
- Glamaの自動発見＋手動キュレーションも当該repoを検出せず

## 具体推奨アクション（ユーザー様）

1. `https://glama.ai/mcp/servers` へ移動し、「Add MCP Server」をclicked
2. GitHub OAuth デバイスフローで `atushi1841` を認証
3. 以下の10repoを1つずつ手動登録（約10分）:
   - mcp-weather-japan, mcp-japan-postal, mcp-japan-holiday, mcp-japan-geospatial, mcp-japan-railway, mcp-japan-fuel, mcp-japan-market, mcp-japan-minimum-wage, mandarake-surugaya-mcp, rakuten-japan-mcp
4. 登録後、`curl 'https://glama.ai/mcp/servers?query=author%3Aatushi1841'` で12件以上を確認

## 代替チャネル（参考）

Glamaが無理でも、以下のチャネルは自動化可能：
- **MCP公式レジストリ**（GitHub: modelcontextprotocol/servers）— PR自動提出可
- **mcp.so** — 検討中（JS描画のため自動化難）
- **dev.to** — 設定済・投稿自動化可（`scripts/devto_weekly_pipeline.py`）

→ 別チャネルへの再配布は critic に提案を依頼

## Verifiability Constraint

- [x] OpenAPI 全エンドポイント確認（https://glama.ai/api/mcp/openapi.json）
- [x] POST /api/mcp/servers = 404（試行済）
- [x] GET /mcp/servers = 200（読取のみ確認）
- [x] 10repoのglama.json push済み・Glama検出404（前回worker実測）
- [x] APIキー作成页面 = 手動UI（https://glama.ai/settings/api-keys）