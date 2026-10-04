# t_7170c363 Verification Evidence Report

## task_info
- task_id: t_7170c363
- title: dev.to英語記事投稿でApify Store外部誘導
- assignee: kensho-revenue-worker
- date: 2026-10-04

## verification_evidence
$ python3 scripts/publish_devto.py reports/journalism/drafts/devto-2026W40-en.md
[DRAFT] /mnt/d/Project2/kensho/reports/journalism/drafts/devto-2026W40-en.md
[META ] title='Japanese Market Data You Can Actually Use: 8 Apify Actors for Scraping Mercari, Yahoo Auctions, Rakuten, and More' tags=['web-scraping', 'data', 'apify', 'japan'] published=False
[BODY ] 4365 chars, 55 lines
[DRY-RUN] --publish 未指定のため投稿しません

$ python3 -c "import urllib.request; req=urllib.request.Request('https://dev.to/atu_ino_ed473db24d76d234a/how-to-scrape-mercari-japan-in-2026-prices-listings-sold-data-no-api-key-1bk8',headers={'User-Agent':'Mozilla/5.0'}); r=urllib.request.urlopen(req); print('HTTP', r.status)"
HTTP 200

$ python3 scripts/publish_devto.py reports/journalism/drafts/devto-2026W40-en.md --publish
[ERR] HTTP 401: {"error":"unauthorized","status":401}

## summary
- **調査結果**: dev.to 英語記事草案 (`devto-2026W40-en.md`) を作成し、8つの Apify Store アクターリンクを埋め込み完了。
- **投稿スクリプト**: `scripts/publish_devto.py` を新規作成し、front matter パース・ドライラン動作確認済み。
- **API認証結果**: `.env` 内の `DEVTO_API_KEY` (値: `cxYHn1sBZaUF...`) は dev.to API により **HTTP 401 Unauthorized** で拒否。キーが無効または失効している。
- **公開記事確認**: 過去に公開された3本 (`#4606013`, `#4760098`, `#4760099`) は Web UI 上で正常にアクセス可能（HTTP 200）。内2本には Apify Store リンク埋め込み確認済み。
- **ブロック要因**: `DEVTO_API_KEY` の再発行が必要（dev.to > Settings > Extensions > Generate API Key）。

## next_action
- 【要ユーザー対応】dev.to の Settings > Extensions にて新しい API Key を発行し、`.env` の `DEVTO_API_KEY` を更新してください。
- 更新後、`python3 scripts/publish_devto.py reports/journalism/drafts/devto-2026W40-en.md --publish --public` で英語記事の自動投稿が完了します。
