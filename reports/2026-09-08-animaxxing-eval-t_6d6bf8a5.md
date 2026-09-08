# 評価レポート: Show HN: Animaxxing – get agents to animate the shit out of your website

- Task: t_6d6bf8a5
- 対象: https://animaxxing.com / HN: https://news.ycombinator.com/item?id=49603561 (score 5, コメント 2)
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（非収益・実装対象外）**
- 実装工数推定: 適用外（実装すべき収益商品なし）

## 対象の実態
**Animaxxing** = johnpolacek 氏の「GSAP で企業サイトをぶっ飛んだアニメーションにする」楽しさのためのオーバー・ザ・トップなデモサイト。
- Next.js 製(Vercel ホスト)。Wikipedia / Craigslist / Hacker News / GitHub 等を過剰アニメーション化した無料デモ + テーマスイッチャー(Bauhaus / cinematic / early web / Strong Bad 等)。全クライアントサイド、パフォーマンス重視の静的Next.js。
- 著者は元 Flash 開発者で、その懐かしさを込めた「ただの実験デモ」と HN コメントで明言。
- 実資産は `johnpolacek/animaxxing-skills`(GitHub, **MIT**: GSAP 対応の page transition / mount→intro→outro→cleanup / split-text / scroll choreography / particle スキル群)。stars 5, forks 1。メッセージは「If you just want the skills → 無料GitHub」。
- 収益モデル: **無し**。pricing / api エンドポイントは全て **404**。課金・広告・購読・有料スキル販売なし。

## 自動化キーワード判定
Hunter フラグ「自動化キーワード: あり」= **誤検出**。中身は「agents がコーディング支援用に使う GSAP スキル(開発ツール内部機能)」で、チュートリアル著名投稿の John Polacek 氏のお遊びデモ。自動収集・自動配信・AIデータ配信とは無関係。スキル判定パターン「開発ツール内部機能記述(エージェント/スキル)→誤検出として除外」に該当。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
Kensho の核(Pythonスクレイピング + LLM要約)が活かせる**スクレイピング対象データが皆無**。
- `robots.txt`/`sitemap.xml`/`rss.xml`/`feed.xml`/`atom.xml`/`api`/`pricing` 全て **HTTP 404**。配信・データのエンドポイントゼロ。Next.js フロントは re-fetch 不要の静的HTMLで、アニメーションはクライアントJS実行。
- 「アニメーション作品ギャラリー」も成立不能: 各デモは既存取りソース(Wikipedia/GitHub等)をブラウザで再テーマ化したもの。ソースは公開ドメインで、お題のデータ自体はコモディティ。集約・付加価値の余地なし。
- 唯一の科学的価値は GSAP スキル群だが、**MIT 無料公開**ゆえ誰でもタダで使える=「再配布/有料化」に価値ゼロ。スクレイピング資産と接続点なし。

### 2) ローンチ手順 — 不成立
Kensho の配置経路(データAPI / 自動化 / 自前FastAPI / Apify/RapidAPI)は全て「データ商品 or 販売ツール」前提。本件は売るものが無い。
- 有料プランが存在せず、その場に導線も無い。OSS(MIT)スキルと競合する位置に「同機能」をセルフホストで出しても、価格差・排他性が一切生まれない。

### 3) 集客 — 不成立
- Kensho の集客アセット(属性データ / CtoA / 既存トラフィック / 既存観客)ゼロ。
- 原サイトの HN score 5 / コメント 2 は観客規模が微小(score<20)。コメントも「楽しさ/遊び心」への反応(2件)で、**「これにお金を払う」需要シグナルは皆無**。スキル配布はジョン氏個人の人気に依存した無料ギブ。

## 結論
Animaxxing は、データ・API・収益モデル(課金/有料スキル/広告すべて無し)・スクレイピング対象が皆無の、MIT 無料 OSS スキルセット + クライアントサイドお遊びデモ。Kensho の「スクレイピング + LLM要約 → データ商品/販売ツール」型非API収益に転換可能な構成要素が**一つも無い**。スキル判定パターン「大企業/個人の無料OSSライブラリ(MIT):収集データ無し・有料化余地なし → 却下」および「自動化ワードは開発ツール内部機能記述 → 誤検出」に完全一致。ランク高フラグは自動化ワード誤検出によるもので、優先評価対象に残す価値なし。

- 成立条件を満たさないため、プロトタイプ/ローンチ手順/集客の3点はいずれも着手しない。

## 検出パイプラインへの推奨除外/優先ルール
- 著名投稿者(John Polacek 等)の「お遊びの過剰デモ + GSAP スキル公開」系 Show HN は、自動化ワード(agents/skills)に騙されず **無料OSS + 収益導線なし + スクレイピング対象データなし** の観点で即却下してよい。
- 「agents / animate the shit out of」等の煽り文案は製品の収益性と無関係。score と収益要素(データ、課金導線)を分離して評価する。

## verification_evidence
$ curl -A "Mozilla/5.0" -o /dev/null -w "%{http_code}" https://animaxxing.com
200
$ curl -s -o /dev/null -w "%{http_code}" https://animaxxing.com/robots.txt
404
$ curl -s -o /dev/null -w "%{http_code}" https://animaxxing.com/sitemap.xml
404
$ curl -s -o /dev/null -w "%{http_code}" https://animaxxing.com/rss.xml
404
$ curl -s -o /dev/null -w "%{http_code}" https://animaxxing.com/feed.xml
404
$ curl -s -o /dev/null -w "%{http_code}" https://animaxxing.com/atom.xml
404
$ curl -s -o /dev/null -w "%{http_code}" https://animaxxing.com/api
404
$ curl -s -o /dev/null -w "%{http_code}" https://animaxxing.com/pricing
404
$ curl -s https://news.ycombinator.com/item?id=49603561
score 5 / comments 2 (whimsy/playfulness only; no paid-demand signal)
$ curl -s https://api.github.com/repos/johnpolacek/animaxxing-skills
license: MIT / stargazers 5 / forks 1 (free OSS, no chargeable surface)

## 元データ
- 実測: curl animaxxing.com root 200(Next.js/Vercel, robots.txt 404, sitemap.xml 404, rss.xml 404, feed.xml 404, atom.xml 404, api 404, api/animations 404, pricing 404)
- HN API/HN HTML item 49603561 (score 5, コメント 2: 「whimsy」「playfulness」のみ)
- GitHub API johnpolacek/animaxxing-skills (MIT, stars 5, forks 1)
