# 検証記録: OtoDock (oto-dock) 非API収益評価（t_fee7c78e）

- 対象: https://github.com/OtoDock/oto-dock / https://otodock.io / HN: https://news.ycombinator.com/item?id=49630606
- 判断: 却下（実装対象外）— Claude Code / Codex を「部門（departments）」で編成して自走させるセルフホスト型エージェントプラットフォーム（"agentic company OS"）。ライセンスは FSL-1.1-Apache-2.0（Fair Source、2年後Apache化）、課金はシート単価（5ユーザーまで恒久無料→Pro €25/mo→Business €199/mo→Enterprise）。Kensho資産（Python scraping + LLM要約）で収集・加工・販売できる公開データセットが存在せず（/rss・/feed・/api すべて404実測、sitemapはマーケティングページ13本のみ）、プロダクト自体の模倣はマルチテナントWebアプリ+エージェントオーケストレーションの数四半期事業 = 月1〜3万円の受動収益商品として不成立（Fair Source/OSS開発プラットフォーム+シート課金却下パターン）。
- 検出は「自動化キーワード: あり」だが、これは製品内部機能（agentsが自動で働く・cron風の自走）の記述であり、自動収集・自動配信サービスではない = スキル所定の誤検出除外枠。

## 3点評価

### 1) プロトタイプ — 不可
- 販売可能なデータが存在しない: otodock.io は root/features/pricing/tutorials/news/enterprise/contact/fair-source/legal系の計13URLのみ（sitemap.xmlで列挙確認）。RSS/Feed/公開APIなし（404実測、robots.txtは /api/ をDisallow）。docs.otodock.io は自产品設置手順書。
- 本体はPython製セルフホストアプリ（GitHub 113 stars / 8 forks / 2026-07-09作成 / FSL-1.1-Apache-2.0）。コード自体は無料配布済みで再配布・有料化余地なし。「Self-host free up to 5 users, forever」がpricingページの明記。
- 模倣はKenshoの資産範囲外: マルチテナントWebアプリ、4種の協働モード、Claude Code/Codex CLIラッパー、音声回線、3Dダッシュボード等、開発者向けインフラ製品のフルスタック長期開発。HNコメントでも「Cloudflare OSに似ている」「agents NOT doing much が重要で deterministic backbone が本丸」「誰が完了検証するのか」といった設計論争が中心で、データ商品性のかけらも無い。

### 2) ローンチ手順 — 不可
- Kenshoの配置経路（データAPI / 自動化スクリプト / 自前FastAPI / Apify/RapidAPI）のいずれにも載らない。載せられるとすれば「AIエージェントOS」という製品そのものの開発になり、SaaS的シート課金事業（営業・エンタープライズ対応・SSO/air-gapped対応付き）。受動収益に非適合。
- 周辺の商品化余地（tutorials/news記事の集約、コミュニティMCP/Agents/Skillsカタログ）も全て自社サイトの無料公開物でコモディティ。

### 3) 集客 — 不可
- HN本体は score 44 / comments 10 と注目度が小さく、観客はAIインフラ開発者層。Kenshoに集客アセット（属性データ・既存トラフィック・CtoA）が皆無。
- 類似の「agent orchestration / company OS」は2026年時点で飽和領域（Cloudflare OS等が言及済み）。個人副収入の切り売り対象外。

## 結論
却下。worker実装タスク（プロトタイプ/ローンチ/集客）は切り出さない。

## verification_evidence

```
$ curl -s 'https://hn.algolia.com/api/v1/items/49630606' | jq -r '.title, .points, .author, .url, .created_at'
Show HN: Self-hosted company OS, Claude Code and Codex agents in departments
44
dimitrismrtzs
https://github.com/OtoDock/oto-dock
2026-09-09T17:57:55.000Z
$ curl -s https://api.github.com/repos/OtoDock/oto-dock | jq '{stars:.stargazers_count, forks:.forks_count, license:.license.spdx_id, created:.created_at, homepage}'
{ "stars": 113, "forks": 8, "license": "NOASSERTION", "created": "2026-07-09T18:10:33Z", "homepage": "https://otodock.io" }
$ curl -s https://raw.githubusercontent.com/OtoDock/oto-dock/main/LICENSE | head -4
# Functional Source License, Version 1.1, Apache 2.0 Future License
## Abbreviation
FSL-1.1-Apache-2.0
Copyright 2026 Dimitrios Mourtzis <legal@otodock.io>
$ for p in "" rss feed api sitemap.xml robots.txt pricing; do curl -s -o /dev/null -w "/%s -> %{http_code}\n" "https://otodock.io/$p"; done
/ -> 200
/rss -> 404
/feed -> 404
/api -> 404
/sitemap.xml -> 200
/robots.txt -> 200
/pricing -> 200
$ curl -s https://otodock.io/sitemap.xml | grep -o '<loc>[^<]*' | sed 's/<loc>//'
https://otodock.io/
https://otodock.io/features
https://otodock.io/pricing
https://otodock.io/tutorials
https://otodock.io/news
https://otodock.io/enterprise
https://otodock.io/contact
https://otodock.io/fair-source
https://otodock.io/legal/privacy
https://otodock.io/legal/terms
https://otodock.io/legal/cookies
https://otodock.io/tutorials/install-otodock-docker-compose
https://otodock.io/news/otodock-is-now-public
$ curl -s https://otodock.io/robots.txt
User-Agent: *
Allow: /
Disallow: /dashboard
Disallow: /admin
Disallow: /api/
Disallow: /verify
Disallow: /reset
Sitemap: https://otodock.io/sitemap.xml
$ curl -s https://otodock.io/pricing | sed 's/<[^>]*>/ /g' | grep -o -E '.{0,60}(€[0-9]+|free forever|Self-host free).{0,60}'
"Simple, seat-based pricing Self-host free up to 5 users, forever. License by seats as your team grows … Community ≤5 users €0 Self-host · free forever … Pro 4–15 users €25 /mo … Business 51–100 users €199 /mo … Enterprise 100+ users, custom terms, air-gapped option, SSO"
$ curl -s 'https://hn.algolia.com/api/v1/items/49630606' | jq -r '.children[] | select(.type=="comment") | .author + ": " + (.text // "")' | sed 's/<[^>]*>//g' | head
bluehatbrit: This seems a lot like Cloudflare OS … keen to understand how this differs aside from not being baked into the Cloudflare estate.
madamelic: … the most critical part is agents NOT doing much and relying on 'boring' deterministic backbones …
NimadFlow: If you organize agents by department, who verifies an agent's 'completion' report? …
nerdsnipe: … my main issue being that agents would go over daily budgets all too often.
```

冒頭から証跡セクション末尾まで言及 task_id は t_fee7c78e（本タスク）のみ。
