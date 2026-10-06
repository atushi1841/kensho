# Revenue Worker 実行記録 2026-10-10

## やったこと
- dev.to internal links 再適用（16本中3本要追記）
- 前回PUT 200/readback=Falseと判定された2本（4798850, 4796617）はGET確認でlink已に存在（誤判定）
- 4797699（429）を再試行 → PUT 200 / readback=True 成功

## 実測値
- 追記対象3本全成功: PUT 200 + readback=True
  - 4803750 (japan-prize-giveaway-scraper)
  - 4803747 (japan-prize-giveaway-scraper)
  - 4797699 (japan-anime-figure-price-data, surugaya-japan-hobby-prices)
- 誤判定だった2本: 4798850, 4796617（既にlink存在）

## 自己レビュー
- readback確認は `body_markdown` grepで正しく判定できる
- 前回レポートのfail判定基準（PUT 200 + readback=False）はraw body取得遅延の可能性あり → script側でgrepで再検証すべき
- dev.to API rate limit: 429は1本のみ、24h以上で回復

## commit
- ebb431e dev.to internal links: 16本再実行、3本PUT 200+readback=True全成功（4797699含む）

## verification_evidence
- `python3 -c "import json;d=json.load(open('reports/apify-seo/devto-links.json'));print([r['id'] for r in d['rows'] if r.get('put_status')==200 and r.get('readback_has_link')])"` → [4803750, 4803747, 4797699]
- `git log --oneline -1` → ebb431e
