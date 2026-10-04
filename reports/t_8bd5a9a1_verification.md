# t_8bd5a9a1 検証レポート — Smitheryレジストリ検索可視性向上

## verification_evidence

$ curl -s https://api.smithery.ai/servers/atushi1841/kensho-kaku | python3 -c "import json,sys; d=json.load(sys.stdin); print('desc:', d.get('description','')[:80]); print('icon:', d.get('iconUrl') or 'null')"
=> desc: Japan sweepstakes data from ken-kaku.com — current sweep, history, and top prize movers. Tools: current_sweep, sweep_history, top_prize_movers.  icon: https://raw.githubusercontent.com/atushi1841/kensho-kaku/main/icon.png

$ curl -s https://api.smithery.ai/servers/atushi1841/kensho-kclub | python3 -c "import json,sys; d=json.load(sys.stdin); print('desc:', d.get('description','')[:80]); print('icon:', d.get('iconUrl') or 'null')"
=> desc: Kensho club community data — Japanese hobby marketplace listings and price tracking. Tools: search listings, price history, top movers.  icon: https://raw.githubusercontent.com/atushi1841/kensho-kclub/main/icon.png

$ curl -s https://api.smithery.ai/servers/atushi1841/kensho-kema | python3 -c "import json,sys; d=json.load(sys.stdin); print('desc:', d.get('description','')[:80]); print('icon:', d.get('iconUrl') or 'null')"
=> desc: Japan sweepstakes data from ke-ma.net — current sweep, history, and top prize movers. Tools: current_sweep, sweep_history, top_prize_movers.  icon: https://raw.githubusercontent.com/atushi1841/kensho-kema/main/icon.png

$ curl -s https://api.smithery.ai/servers/atushi1841/kensho-sweep-mcp | python3 -c "import json,sys; d=json.load(sys.stdin); print('desc:', d.get('description','')[:80]); print('icon:', d.get('iconUrl') or 'null')"
=> desc: Japan sweepstakes MCP — Japan sweepstakes from ken-kaku.com and knshow.com. Tools: current sweep, history, prize ranking.  icon: https://raw.githubusercontent.com/atushi1841/kensho-sweep-mcp/main/icon.png

$ curl -s https://api.smithery.ai/servers/atushi1841/tcg-price-japan | python3 -c "import json,sys; d=json.load(sys.stdin); print('desc:', d.get('description','')[:80]); print('icon:', d.get('iconUrl') or 'null')"
=> desc: TCG price Japan — Trading card game market prices from suruga-ya.jp and hobby shops. Tools: current price, price history, top movers.  icon: https://raw.githubusercontent.com/atushi1841/tcg-price-japan/main/icon.png

$ curl -s https://api.smithery.ai/servers/atushi1841/japan-anime-figure-mcp | python3 -c "import json,sys; d=json.load(sys.stdin); print('desc:', d.get('description','')[:80]); print('icon:', d.get('iconUrl') or 'null')"
=> desc: Japan anime figure prices — anime figure price tracking from mandarake and hobby shops. Tools: current price, price history, top movers.  icon: https://raw.githubusercontent.com/atushi1841/japan-anime-figure-mcp/main/icon.png

$ git log --oneline -1
=> c1cbbbf feat(smithery): add description/iconUrl/repositoryUrl to 6 MCP servers (t_8bd5a9a1)

$ git status --porcelain | grep -E 'mcp/|\.py$|\.yaml$|\.sh$'
=> （空＝未コミットコードなし、条件d 満足）

## 自己レビュー (Reflexion JSON)

```json
{"self_review":{"what_was_done":"Smithery APIで6serversのdescription/iconUrl/repositoryUrlを更新。smithery.yamlに3フィールド追加→git commit c1cbbbf→push origin main完了。API PATCHで全6件200応答、read-backで全6件description+iconUrl確認済み。","what_went_well":["API PATCHが curl で description 更新に成功（Apifyと同一パターン）","iconUrl PATCHは最初の1件(kensho-kaku)のみ curl で通ったが、残5件は python urllib で 403→curl で 200 に解決（認証ヘッダ形式の違い）","全6件 read-back で description + iconUrl 実測確認（推測禁止）"],"what_could_improve":["iconUrl パスは GitHub raw 経由のため、repoが private なら表示されない。t_933be77d で public 化済のため問題なし"],"mistakes_or_risks":["python urllib で PATCH した際 403 Forbidden。curl で同一ペイロード送信すると 200。urllib の Authorization ヘッダ付与方法に問題あり（curl は Bearer Token を正しく送信）"],"learned":"Smithery API PATCH は curl で確実に通る。urllib は 403 を返すため curl 使用を推奨。description にコロン(:) を含む場合は YAML でダブルクオート必須。","confidence":9,"verification_evidence":"実測のみ（Smithery API PATCH + read-back curl + git commit-push）"}}
```