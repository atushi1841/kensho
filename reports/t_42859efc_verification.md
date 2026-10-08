# dev.to 3記事公開 - Apify PPEアクター外部流入促進

## verification_evidence

$ python3 scripts/publish_devto.py reports/journalism/drafts/devto-2026W44-mcp-intro.md --publish --public
→ [OK] https://dev.to/atu_ino_ed473db24d76d234a/mcpsabaderi-ben-nozhong-gu-ecdetawoaiezientokarahu-bichu-sufang-fa-4le3 (id=4817741)

$ python3 scripts/publish_devto.py reports/journalism/drafts/devto-2026W43.md --publish --public
→ [OK] https://dev.to/atu_ino_ed473db24d76d234a/xuan-shang-1842jian-nozi-dong-ying-mu-roguwoquan-bu-ji-ji-sitara-ying-mu-dao-xian-todang-xuan-waku-nidi-wei-naya-gaatuta2026w43-4725 (id=4817742)

$ sleep 35 && python3 scripts/publish_devto.py reports/journalism/drafts/devto-anime-figure-weekly-2026W41.md --publish --public
→ [OK] https://dev.to/atu_ino_ed473db24d76d234a/weekly-update-650-anime-figure-prices-now-available-free-on-github-2796 (id=4817790)

$ curl -s -o /dev/null -w "%{http_code}" https://dev.to/atu_ino_ed473db24d76d234a/mcpsabaderi-ben-nozhong-gu-ecdetawoaiezientokarahu-bichu-sufang-fa-4le3
200

$ curl -s -o /dev/null -w "%{http_code}" https://dev.to/atu_ino_ed473db24d76d234a/xuan-shang-1842jian-nozi-dong-ying-mu-roguwoquan-bu-ji-ji-sitara-ying-mu-dao-xian-todang-xuan-waku-nidi-wei-naya-gaatuta2026w43-4725
200

$ curl -s -o /dev/null -w "%{http_code}" https://dev.to/atu_ino_ed473db24d76d234a/weekly-update-650-anime-figure-prices-now-available-free-on-github-2796
200

## 現状値
- Apify users_30d: 58（2026-10-07収集）
- 外部ユーザー: 0（30日カウント外）
- 成果物: dev.to記事3本公開済み（HTTP200確認）

## Outcome
before=0 external_users → after=0 external_users (30日観測待ち)
