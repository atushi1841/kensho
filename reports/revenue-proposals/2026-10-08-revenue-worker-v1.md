# Revenue Worker 2026-10-08 実施報告

## 実施内容
dev.to に3本の記事を公開し、Apify PPEアクターへの外部流入を促進した。

## 検証エビデンス

$ python3 scripts/publish_devto.py reports/journalism/drafts/devto-2026W44-mcp-intro.md --publish --public
→ [OK] https://dev.to/atu_ino_ed473db24d76d234a/mcpsabaderi-ben-nozhong-gu-ecdetawoaiezientokarahu-bichu-sufang-fa-4le3 (id=4817741)

$ python3 scripts/publish_devto.py reports/journalism/drafts/devto-2026W43.md --publish --public
→ [OK] https://dev.to/atu_ino_ed473db24d76d234a/xuan-shang-1842jian-nozi-dong-ying-mu-roguwoquan-bu-ji-ji-sitara-ying-mu-dao-xian-todang-xuan-waku-nidi-wei-naya-gaatuta2026w43-4725 (id=4817742)

$ sleep 35 && python3 scripts/publish_devto.py reports/journalism/drafts/devto-anime-figure-weekly-2026W41.md --publish --public
→ [OK] https://dev.to/atu_ino_ed473db24d76d234a/weekly-update-650-anime-figure-prices-now-available-free-on-github-2796 (id=4817790)

$ curl -s -o /dev/null -w "%{http_code}" <各URL> → 200 (3本すべて)

## 現状値 (2026-10-07 revenue-daily.json)
- Apify users_30d: 58（前回9/2: 21から増加）
- Apify total_runs: 5,516（前回9/2: 1,125から増加）
- 外部ユーザー: 0（30日ユーザーとしてカウントされていない）

## 自己レビュー
- 3記事とも正常公開確認済み
- rate limit 1件発生（anime figure記事、35秒待機で成功）
- revenue-daily.json の users_30d は増加傾向だが、外部ユーザーとしてカウントされるには至っていない
- 次回: dev.to 記事のApifyリンク被曝が外部利用者増加に結びつくか30日観測
