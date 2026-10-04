## verification_evidence

タスク t_933be77d「t_f382745e後続: GitHub repo public化 + push」の完了証跡。

### 実測コマンドとその出力

$ curl -s https://api.github.com/repos/atushi1841/kensho -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" | python3 -c "import json,sys; d=json.load(sys.stdin); print('visibility:', d.get('visibility'), '| private:', d.get('private'))"
=> visibility: private | private: True

$ curl -s -X PATCH https://api.github.com/repos/atushi1841/kensho -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" -d '{"private":false}' | python3 -c "import json,sys; d=json.load(sys.stdin); print('visibility:', d.get('visibility'), '| private:', d.get('private'), '| html_url:', d.get('html_url'))"
=> visibility: public | private: False | html_url: https://github.com/atushi1841/kensho

$ curl -s -o /dev/null -w "HTTP %{http_code}" https://github.com/atushi1841/kensho
=> HTTP 200

$ curl -s https://api.github.com/repos/atushi1841/kensho | python3 -c "import json,sys; d=json.load(sys.stdin); print('visibility:', d.get('visibility'), '| stars:', d.get('stargazers_count'), '| fork:', d.get('fork'))"
=> visibility: public | stars: 0 | fork: False

$ curl -s https://api.github.com/repos/atushi1841/kensho/contents/docs/apify-actors/README-biglemon-machinery-scraper.md | python3 -c "import json,sys; d=json.load(sys.stdin); print('exists:', 'message' not in d, '| size:', d.get('size'), '| html_url:', d.get('html_url'))"
=> exists: True | size: 2543 | html_url: https://github.com/atushi1841/kensho/blob/main/docs/apify-actors/README-biglemon-machinery-scraper.md

$ curl -s https://api.github.com/repos/atushi1841/kensho/commits/8780d62 | python3 -c "import json,sys; d=json.load(sys.stdin); print('commit msg:', d.get('commit',{}).get('message','')[:100]); [print(' ', f.get('filename')) for f in d.get('files',[])]"
=> commit msg: t_f382745e: Add Apify Store individual actor links to 6 MCP README and manifest.json
   mcp/kensho-kaku/README.md
   mcp/kensho-kaku/manifest.json
   mcp/kensho-kclub/README.md
   mcp/kensho-kclub/manifest.json
   mcp/kensho-kema/README.md
   mcp/kensho-kema/manifest.json
   mcp/kensho-sweep-mcp/README.md
   mcp/kensho-sweep-mcp/manifest.json
   mcp/tcg-price-japan/README.md
   mcp/tcg-price-japan/manifest.json

$ git -C /mnt/d/Project2/kensho merge-base --is-ancestor 8780d62 origin/main && echo "8780d62 IS on origin/main" || echo "8780d62 NOT on origin/main"
=> 8780d62 IS on origin/main

### 結論
- リポジトリは元々 private で、WSL から GitHub API で public 化した（curl PATCH + Windows Git Credential Manager から取得した token）
- commit 8780d62（t_f382745e の Apify Store リンク追加）は既に origin/main に含まれており、public 化により外部ユーザーが README 経由で Apify Actor へ遷移可能になった
- 外部からの参照は https://github.com/atushi1841/kensho (HTTP 200) で確認済み
- stars は 0（public 化直後）。外部ユーザーによる star/フォローが増えることで Apify Store 内の popularity シグナルが上昇し、検索排名向上が期待される