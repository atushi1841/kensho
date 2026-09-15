# 検証記録: AttaLambda（Show HN: a language where types and data are made of untyped lambdas）非API収益評価（t_cf4993e8）

- 対象: https://attalambda.com / GitHub: https://github.com/kserrec/attalambda / HN: https://news.ycombinator.com/item?id=49699477（score 25 / コメント0）
- 判断: 却下（実装対象外）— 中身は個人趣味プロジェクトのオープンソースプログラミング言語（Racket実装、Apache-2.0、GitHub star 1・2026-08-24作成新規）。「型もデータも無型ラムダで構成」という言語設計の知的遊戯で、販売物・データ・API・収益フックが構成のどこにも存在しない。スキル既定の却下パターン「OSS開発フレームワーク/OSSライブラリ（Apache/MIT等で無料配布）: 収集データ・有料化余地なし → 却下」の言語処理系版そのもの。
- 検出側の「自動化キーワード: あり」は誤検出。本文の語彙（control flow / macros / computation is done automatically 系）は言語内部の計算機構の説明で、自動収集・自動配信サービスではない。HNスレッドはコメント0=対話も収益シグナルも無し。

## 3点評価

### 1) プロトタイプ — 不可
- 対象サイトは完全静的HTML 4ページ（index/language/examples/get-started、計2KB程度）。sitemap.xml / rss / feed / docs / playground すべて404で、機械可読データもインターラクティブAPIも存在しない。売れるデータセットがそもそも無い。
- 配布物は GitHub Releases の Linux x86-64 バイナリ（Racketランタイム同梱）で Apache-2.0=自由再配布可。Kensho資産（Python scraping + LLM要約 + X運用）を接続する隙間がない: スクレイピング対象なし、要約対象の継続更新データなし、自動化可能な運用フローなし。
- 独占性・再現困難性はゼロ——むしろ「誰でもタダで使える」こと自体が製品の目的（オープンソース言語の普及）。

### 2) ローンチ手順 — 不可
- Kensho 配置経路（データAPI / 自動化 / 自前FastAPI / Apify / RapidAPI / ニッチSaaS）のどれにも乗らない。言語処理系ビジネスは Rust/Go 級のコミュニティ運営＋長期維持資本が要る本業事業で、月1-3万円の受動収益スコープ外。
- 収益モデル自体が作者から提示されていない（HN本文・サイトに価格・スポンサー・有償プランの記述一切無し）。OSS無償配布のlang play project に転用可能な収益源はない。

### 3) 集客 — 不可
- HN score 25・トップレベルコメント0・GitHub star 1・リポジトリ作成3週間で、観客規模が微小。しかもCloudflare managed robots.txt が ai-train=no / GPTBot・ClaudeBot等 Disallow を宣言しており、コンテンツのAI収集的転用にも消極的なサイト方針。
- 集客アセット（属性データ・CtoA・既存トラフィック）は移管不能。言語の話題性は「PL理論趣味層」向けで、Kensho の観客（懸賞/自動化系Xフォロワ）と重ならない。

## 結論
却下。worker 実装タスク（プロトタイプ/ローンチ/集客）は切り出さない。
検出側の教訓（hunterへ回付）: 「Show HN: I made a programming language / interpreter / compiler」系は Apache/MIT で無料配布されるOSS趣味プロジェクトが大半で、収益フック（価格・API・データ・有償ホスティング）が本文に1つも無いものはスコアや「自動化」語彙の含有に関係なく自動除外してよい（本件 star 1 / コメント0 / 新規3週間が裏付け）。既存の除外パターン（TokenDelivery=t_833a07b6、OSS推論ホスティング=t_0bd69b5f）と同枠の「OSS無償配布ゲート」。

## verification_evidence

```
$ curl -sL --max-time 20 -o /tmp/atta_root.html -w "root: %{http_code} %{size_download}b %{url_effective}\n" https://attalambda.com
root: 200 2071b https://attalambda.com/（完全静的HTML、footer "AttaLambda is open source under the Apache License 2.0"）
$ curl -s --max-time 15 "https://hn.algolia.com/api/v1/items/49699477"
hn: 200 4321b（"author":"kserrec","points":25,"children":[] =コメント0、本文 "I made a programming language!<p>I call it AttaLambda."）
$ for p in robots.txt sitemap.xml rss feed docs playground; do curl -s -o /dev/null -w "/$p: %{http_code}\n" "https://attalambda.com/$p"; done
/robots.txt: 200 /sitemap.xml: 404 /rss: 404 /feed: 404 /docs: 404 /playground: 404（機械可読データ・エンドポイント全無し）
$ curl -s --max-time 10 https://attalambda.com/robots.txt
Cloudflare Managed content: "Content-Signal: search=yes,ai-train=no,use=reference" / "User-agent: GPTBot Disallow: /" / "User-agent: ClaudeBot Disallow: /"
$ curl -s --max-time 15 "https://api.github.com/repos/kserrec/attalambda"
gh: 200 → full_name=kserrec/attalambda, stargazers_count=1, forks_count=0, language=Racket, license=Apache-2.0, created_at=2026-08-24, open_issues=0
$ curl -sL --max-time 15 -o /tmp/atta_gs.html -w "get-started: %{http_code} %{size_download}b\n" https://attalambda.com/get-started.html
get-started: 200 4392b（内容は GitHub Releases tar.gz 手動ダウンロード+sha256sum 検証手順のみ。価格・API・有償プランの記述ゼロ）
```

冒頭から証跡セクション末尾まで言及 task_id は t_cf4993e8（本タスク）のみ。
