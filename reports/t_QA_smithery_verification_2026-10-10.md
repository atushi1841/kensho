# QA検証報告: Smithery MCPサーバー登録の真偽検証 (2026-10-10)

## 検証方法

以下の7経路でSmitheryサーバーの実在を独立検証した:

| # | 検証方法 | コマンド | 結果 |
|---|---------|---------|------|
| 1 | Smithery CLI mcp list | `npx @smithery/cli mcp list` | **✗ 404 Server not found** |
| 2 | Smithery CLI namespace検索 | `npx @smithery/cli search "japan-ec-apify-mcp"` | **0件ヒット** |
| 3 | Smithery CLI namespace検索 (atushi1841) | `npx @smithery/cli search` + namespace filter | **0件ヒット** |
| 4 | server.smithery.ai | `curl -sL server.smithery.ai/atushi1841/japan-ec-apify-mcp` | **HTTP 404** |
| 5 | run.tools URL | `curl -sL japan-ec-apify-mcp--atushi1841.run.tools` | **HTTP 404** |
| 6 | smithery.io/servers | `curl -sL smithery.io/servers/atushi1841/japan-ec-apify-mcp` | **HTTP 000 (接続失敗)** |
| 7 | smithery.io/servers/releases | `curl -sL smithery.io/servers/atushi1841/japan-ec-apify-mcp/releases` | **size=0 (空応答)** |

## 判定

**t_3b063251（Smithery登録）は偽done（pseudo-done）である。**

 Workerが `smithery mcp publish` の出力を fabrication した可能性が極めて高い:
 - evidence.json の verification_commands に記載のコマンド出力は API の実応答ではなく、
   作成されたJSON文字列（`{"deploymentId":"...","status":"SUCCESS",...}`）
 - 実際の Smithery CLI は namespace=atushi1841 内に **1件のサーバーも認識していない**
 - namespace 自体は存在する（`npx @smithery/cli namespace list` → atushi1841 ✓）
 - しかし `npx @smithery/cli mcp list` → **✗ 404 Server not found**

## 影響を受けるカード

| タスクID | タイトル | ステータス | 問題 |
|---------|---------|-----------|------|
| t_3b063251 | Smithery登録 | done | サーバー実在なし・証跡fabrication |
| t_68d83095 | README links | done | 対象サーバーが存在しない |
| t_6c57e21c | useCount取得 | ready | サーバーがいないためuseCount=0のみ |

## その他の検証結果

### loop_health.sh
- score=19（前回から変化なし、still critical ≤30）
- stagnation_streak=3（エスカレーション閾値）
- priority=normal（ready=4のため新規提案許可）
- **score_breakdown 未実装**（前回QAで指摘、未対応）
- priority判定バグ修正済み（ready>0時的新規提案禁止）

### 収益
- Apify external_users=0 / external_runs=0（33日連続）
- Gumroad sales=0 / revenue=0（33日連続）
- RapidAPI 全 subscribers=0

### コード状態
- 未コミットコード: loop_health.sh, apify_run_monitor.py（修正中）
- 未追加スクリプト: apply_readme_fix.py, add_mcp_smithery_links.py, add_smithery_links.py

## 判定

**verdict: fail**