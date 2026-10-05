# t_16f7a085: Apify Actor向けMCPサーバー統合 — 検証レポート

## verification_evidence

$ cd /mnt/d/Project2/kensho && git commit -m "t_16f7a085: add kensho-apify MCP server wrapping Apify Actors"
[gh-pages fade75d] t_16f7a085: add kensho-apify MCP server wrapping Apify Actors
 7 files changed, 310 insertions(+), 1 deletion(-)

$ git push origin gh-pages
To https://github.com/atushi1841/kensho.git
   c453990..fade75d  gh-pages -> gh-pages

$ curl -s "https://api.github.com/repos/atushi1841/kensho/contents/mcp/kensho-apify?ref=gh-pages" | python3 -c "import json,sys; d=json.load(sys.stdin); print([x['name'] for x in d])"
['README.md', 'manifest.json', 'pyproject.toml', 'requirements.txt', 'server.py']

$ curl -s "https://api.github.com/repos/atushi1841/kensho/branches/gh-pages" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['commit']['sha'][:7])"
fade75d

$ python3 -m py_compile mcp/kensho-apify/server.py && echo "py_compile OK"
py_compile OK

$ curl -s "https://raw.githubusercontent.com/atushi1841/kensho/gh-pages/site/index.html" | grep -c "kensho-apify"
1

$ git -C /mnt/d/Project2/kensho log --oneline -1
fade75d t_16f7a085: add kensho-apify MCP server wrapping Apify Actors

## 実装内容

- `mcp/kensho-apify/server.py`: Apify ActorをラップするMCPサーバー（list_actors / run_actor / get_run / get_dataset の4ツール）
- `mcp/kensho-apify/manifest.json`: MCPB v0.4 準拠マニフェスト（Smithery登録用）
- `mcp/kensho-apify/README.md`: ドキュメント
- `mcp/kensho-apify/pyproject.toml` / `requirements.txt`: 依存定義
- `site/index.html`: MCP一覧にkensho-apify追加

## 検証結果

- GitHub API経由でgh-pagesブランチに全ファイルが確認済み（5ファイル）
- py_compile: OK
- site/index.html: kensho-apifyエントリ追加済み（grep count=1）
- コミット: fade75d（push済み）

## 次のステップ

- Smitheryレジストリ（smithery.ai）への登録は手動またはAPI経由
- mcp.soレジストリへの登録は別途
- t_050398fc（HF_TOKEN未設定）はユーザー対応待ち
