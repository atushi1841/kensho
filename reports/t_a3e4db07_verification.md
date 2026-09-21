# t_a3e4db07 検証証跡レポート — MCPマーケットプレイス登録

task: t_a3e4db07 (既存MCP資産のマーケットプレイス登録によるAIエージェント流通獲得)
assignee: kensho-worker
対象資産: github.com/atushi1841/japan-market-mcp (GitHub公開済み, リモートHTTP MCP)

## 対象コードとデプロイ

保管庫整理(getreadiness)は前runで commit c192b51 にて実施済み・origin/mainへpush済み:
  llms-install.md / .well-known/mcp.json (16ツール記載) / docs/logo.png (400x400) / README endpoint修正

実測: deployment is live (MCP initialize応答), 16ツール全てtools/listで確認。

## verification_evidence

### 1. readinessコミットとpush状態

$ git -C /mnt/d/Project2/japan-market-mcp log --oneline -3
> c192b51 feat(mcp): marketplace readiness — fix endpoint URL to hyphen form, add llms-install.md + .well-known/mcp.json discovery manifest, add 16-tool coverage (incl. prize giveaways), add 400x400 Cline marketplace logo
> 5db78df feat(mcp): add 4th JP dataset — MAFF fresh produce wholesale market report
> d06547d chore: ignore .mypy_cache

$ git -C /mnt/d/Project2/japan-market-mcp status -sb | head -1
> ## main...origin/main

$ git -C /mnt/d/Project2/japan-market-mcp log origin/main..HEAD --oneline
> (空 = HEAD == origin/main, 受け入れコミットpush済み)

### 2. 本番MCPエンドポイント疎通(initialize)

$ curl -s -X POST https://fruitful-quintessence--japan-market-mcp.apify.actor/mcp -H "Authorization: Bearer $APIFY_TOKEN" -d '{initialize}'
> event: message
> data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18","serverInfo":{"name":"japan-market-mcp","version":"3.4.7"}}}

### 3. 16ツール確認(tools/list)

$ curl -s -X POST https://fruitful-quintessence--japan-market-mcp.apify.actor/mcp -H "mcp-session-id: ..." -d '{"method":"tools/list"}'
> "name":"get_japan_prize_giveaway_stats" / "name":"search_rakuten_items" / "name":"get_maff_market_report" / "name":"search_camera_market" ... 全16ツール

$ grep -o '"name":"[a-z_]*"' /tmp/mcp_tools.txt | sort -u | wc -l
> 16

### 4. Cline MCP Marketplace登録(submission issue)

$ gh issue create --repo cline/mcp-marketplace --title "[Server Submission]: japan-market-mcp — Cross-Shop Japan Price Comparison (16 tools)" --body-file /tmp/cline_issue_body.md
> created: #2593 https://github.com/cline/mcp-marketplace/issues/2593

$ gh api "repos/cline/mcp-marketplace/issues/2593" -q '.state + "|" + .user.login + "|" + .html_url'
> open|atushi1841|https://github.com/cline/mcp-marketplace/issues/2593

$ gh api "repos/cline/mcp-marketplace/issues/2593" -q '.title'
> [Server Submission]: japan-market-mcp — Cross-Shop Japan Price Comparison (16 tools)

### 5. ロゴ配信とリポジトリ公開性(認証なしアクセス)

$ curl -s -o /dev/null -w "%{http_code} %{content_type}" https://raw.githubusercontent.com/atushi1841/japan-market-mcp/main/docs/logo.png
> 200 image/png

$ file /mnt/d/Project2/japan-market-mcp/docs/logo.png
> PNG image data, 400 x 400, 8-bit/color RGB, non-interlaced

$ env -u GH_TOKEN curl -s -o /dev/null -w "%{http_code}" https://api.github.com/repos/atushi1841/japan-market-mcp
> 200 (公開リポジトリ・認証なしで参照可)

### 6. 既存重複確認

$ gh api "repos/cline/mcp-marketplace/issues?state=all&creator=atushi1841"
> [] (本登録前の既存submission無し → #2593が初回登録)
