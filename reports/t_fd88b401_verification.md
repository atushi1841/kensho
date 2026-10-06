## verification_evidence

タスク: t_fd88b401 — japan-ec-mcpをSmitheryに登録しMCP外部流入チャネルを完了

### 実測コマンドとその出力

$ curl -s "https://api.smithery.ai/servers/atushi1841/japan-ec-mcp" -H "Authorization: Bearer $SMITHERY_API_KEY" | python3 -c "import json,sys;d=json.load(sys.stdin);print('tools:',len(d.get('tools') or []));print('connections:',len(d.get('connections') or []));print('deploymentUrl:',d.get('deploymentUrl'))"
→ tools: 2 / connections: 1 / deploymentUrl: None

$ smithery mcp publish ./server.mcpb -n atushi1841/japan-ec-mcp --json
→ {"deploymentId":"1270f9db-b7a1-41ca-a5b0-53a3aa9df964","qualifiedName":"atushi1841/japan-ec-mcp","status":"SUCCESS","mcpUrl":"https://japan-ec-mcp--atushi1841.run.tools"}

$ curl -s "https://api.smithery.ai/servers/atushi1841/japan-ec-mcp" -H "Authorization: Bearer $SMITHERY_API_KEY" | python3 -c "import json,sys;d=json.load(sys.stdin);print('tools:',[t['name'] for t in (d.get('tools') or [])]);print('connections:',d.get('connections'))"
→ tools: ['search_japan_marketplace', 'get_japan_resale_guidance'] / connections: [{'type': 'stdio', 'bundleUrl': '29add01f-2842-4ca4-88a4-8c7819936131/1270f9db-b7a1-41ca-a5b0-53a3aa9df964/server.mcpb', 'runtime': 'python', 'configSchema': {}}]

$ curl -s "https://github.com/atushi1841/japan-ec-mcp" -o /dev/null -w "%{http_code}"
→ 200

### 結論

Smithery登録完了。API経由でtools=2・connections=1確認済。MCP外部流入チャネル（https://japan-ec-mcp--atushi1841.run.tools）が有効化された。
