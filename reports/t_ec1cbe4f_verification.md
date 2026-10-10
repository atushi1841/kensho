# t_ec1cbe4f: Apify StoreカタログGitHub Pages公開完了（QA検証 v1）

## verification_evidence

### 完了条件検証（QA実測）

- **HTTP 200確認**: `curl -sI https://atushi1841.github.io/kensho/ | head -1` → `HTTP/2 200` ✅
- **Actor数確認**: `curl -sL https://atushi1841.github.io/kensho/ | grep -oP '"url": "https://apify\.com/[^"]+"' | wc -l` → `85` ✅
- **GitHub Pagesソース確認**: `gh api repos/atushi1841/kensho/pages | python3 -c "import json,sys; d=json.load(sys.stdin); print('source branch:', d['source']['branch'])"` → `source branch: gh-pages` ✅
- **gh-pagesブランチ内容確認**: `gh api repos/atushi1841/kensho/contents/index.html?ref=gh-pages | python3 -c "import json,sys,base64; d=json.load(sys.stdin); c=base64.b64decode(d['content']).decode(); print('apify.com count:', c.count('apify.com'))"` → `apify.com count: 85` ✅
- **ローカルカタログ確認**: `grep -oP '"url": "https://apify\.com/[^"]+"' /mnt/d/Project2/kensho/catalog-output/index.html | wc -l` → `85` ✅
- **evidence.json修正**: `evidence_hashes` に sha256 ハッシュを追加（旧: git commit SHA → 新: ファイル sha256）→ guard j PASS ✅

### 3軸評価

| 軸 | スコア | 根拠 |
|-----|--------|------|
| technical | **9** | HTTP 200・85 actors・gh-pages ブランチ更新・guard PASS all conditions |
| business_kpi | **8** | Apify Storeカタログの外部可視性向上（85 actors → GitHub Pagesで公開） |
| cost_efficiency | **9** | 既存Apify API + 既存HTML生成スクリプト再利用、新規コード最小 |

### 観点別分割検証

| 観点 | スコア | 根拠 |
|------|--------|------|
| コード品质 | 9 | catalog-output/index.html は静的HTML+JS、死んだコードなし |
| BOT検出リスク | 10 | API呼び出しのみ（アクションなし） |
| 設計一貫性 | 9 | 既存Apify API + GitHub Pagesブランチ継承 |
| テスト充足 | 9 | 85 actors 実測（curl+gh api 独立検証） |
| ライブ計測 | 9 | https://atushi1841.github.io/kensho/ HTTP 200 実測 |

### 実測コマンド（6組）

```bash
$ curl -sI https://atushi1841.github.io/kensho/ | head -1
HTTP/2 200

$ curl -sL https://atushi1841.github.io/kensho/ | grep -oP '"url": "https://apify\.com/[^"]+"' | wc -l
85

$ gh api repos/atushi1841/kensho/pages | python3 -c "import json,sys; d=json.load(sys.stdin); print('source branch:', d['source']['branch'])"
source branch: gh-pages

$ sha256sum /mnt/d/Project2/kensho/catalog-output/index.html
ce15e6346e9dc9c3f3ae4ea0334b4117073304a33689ec78dda33bac847d68bb  /mnt/d/Project2/kensho/catalog-output/index.html

$ sha256sum /mnt/d/Project2/kensho/reports/t_ec1cbe4f_verification.md
da83aa969d11e7f1e2c3ad75253fd54363e7735eb7958eb75ed6e6cec7f8b79e  /mnt/d/Project2/kensho/reports/t_ec1cbe4f_verification.md

$ sha256sum /mnt/d/Project2/kensho/reports/t_ec1cbe4f_evidence.json
138fe198c9e5b6157c1ebc09590085c0004eaaa95e76ff8cd38dfb7163b348e8  /mnt/d/Project2/kensho/reports/t_ec1cbe4f_evidence.json
```

### 成果物
- `/mnt/d/Project2/kensho/catalog-output/index.html` — 85 actors catalog（sha256: ce15e634...）
- `/mnt/d/Project2/kensho/reports/t_ec1cbe4f_verification.md` — 本検証レポート
- `/mnt/d/Project2/kensho/reports/t_ec1cbe4f_evidence.json` — 機械可読ハンドオフ（guard j PASS）
- GitHub Pages: `https://atushi1841.github.io/kensho/`（HTTP 200、85 actors）

### 成功指標
- HTTP 200: ✅
- Actor数: 9 → 85 (+76件)
- Live URL: https://atushi1841.github.io/kensho/

### 失敗時代替案
- GitHub Pagesが利用不可の場合は、japan-market-dataリポジトリのgh-pagesブランチにカタログを配置（既存チャネル経由で公開継続）