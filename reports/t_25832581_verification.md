# t_25832581 verification evidence

## verification_evidence

**Task**: t_25832581 - Register each repo on Glama via List it for free or GitHub index

### 実施内容
Glama MCPサーバー登録の自動化可能性を検証。

### 実測結果

$ curl -s https://glama.ai/api/mcp/openapi.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('Endpoints:', list(d.get('paths',{}).keys()))"
→ GET /v1/servers / GET /v1/connectors / GET /v1/instances / POST /v1/telemetry/usage のみ。POST/PUT/DELETE不存在。

$ curl -s -o /dev/null -w '%{http_code}' https://glama.ai/api/mcp/servers
→ 404（エンドポイント不存在）

$ python3 -c "import urllib.request,re; html=urllib.request.urlopen('https://glama.ai/mcp/servers?query=author%3Aatushi1841',timeout=15).read().decode(); items=re.findall(r'\"url\":\"(https://glama\.ai/mcp/servers/[^\"]+)\"', html); print(f'JSON-LD: {len(set(items))}')"
→ JSON-LD unique URLs: 5

### 判定
Workerのblocked判定( needs_input )は正当。Glama新規登録はGitHub OAuthを介したWeb UI操作が必須で自動化不可。
カードの完了条件「All repos from unlisted_repos.txt are listed on Glama」は不充足（5/10）。
→ このカードはblocked維持が正解。force_completeは偽done。

### 申し送り
- ユーザー手動submitが必要: https://glama.ai/mcp/servers → 「Add MCP Server」→ GitHub OAuth
- 10reposを1つずつ手動登録（約10分）
- 登録後確認: `curl -s "https://glama.ai/mcp/servers?query=author%3Aatushi1841" | grep -oE "href=\"/mcp/servers/[^\"]+\"" | sort -u | wc -l` → 12以上を目標
- 代替チャネル: MCP公式レジストリ（GitHub PR自動提出可）/ dev.to（設定済・自動投稿可）
