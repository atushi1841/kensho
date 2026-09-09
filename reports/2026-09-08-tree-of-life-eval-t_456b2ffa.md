# 評価レポート: Show HN: Interactive Tree of Life (ptree.org)

- Task: t_456b2ffa
- 対象: https://ptree.org/ / HN: https://news.ycombinator.com/item?id=49559069 (score 89, コメント ~23)
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（非収益・実装対象外。worker 実装タスクへ切り出さない）**
- 実装工数推定: 適用外（着手すべき収益商品なし）

## 対象の実態
**Ptree** = 11系統の分類木（学校で学ぶ plant/animalia 等のカテゴリ分類 + 系統進化の phylogenetic 木）を1枚のインタラクティブな樹形図に統合し、41の視覚プロパティ（生息地・栄養・サイズ・寿命・鳥の垂直分布・魚の水深等）を数百の生物学的形質とソースから重ねて表示する Web 可視化ツール。バックエンドは 800GB の生データを 9 ステップのビルドで蒸留した配信系。

- 実体: フロントエンド SPA + PWA（重い JS バンドル、871 行の index.html）。**サイトそのものがデータ商品**で、任意の生物を検索して系統・形質・画像をビジュアル表示する教育ツール。
- 収益要素: ページ実測で価格・サブスク・有料版・寄付・サインイン・プレミアム・ダウンロード・エクスポート・ライセンス記載**一切なし**。plausible analytics のトラッキングのみ埋め込み。
- 配布/利用: 完全無料。作者は 1997 年から稼働する人気アプリ periodic table「ptable.com」の作者（HN コメント確認）。
- 競合: OneZoom（Open Tree of Life/OTL ベースの既存オープン可視化、HN コメントで言及）。優位差は UX の精巧さのみ。

## データの出所・スクレイピング対象（決定打）
- **公開データ API・DS・エクスポート端点が実測で全て 404**：/api, /data, /data.json, /download, /rss.xml, /feed すべて 404。JS バンドル中の "api" 参照は bespoke データ API ではなく **plausible アナリティクス**の pageview 送信（`location.origin` 向け）のみ。
- **独占・再現困難な収集対象データが存在しない**: 表示される分類・形質・画像データ自体は公開ソース由来（HN コメントで Wikipedia/Wikidata、NCBI、Open Tree of Life/OTT 等が確認）。800GB 生データの「アグリゲーション+91形質キュレーション」は工数的に重いが、全入力が公開オープンソースのため専門資本があれば誰でも再現可能で、Kensho に優位性なし。
- robots.txt は Cloudflare 管理の content-signal（search=yes, ai-train=no, use=reference）。データ収集・AI 入力に対しトーン上は保守的。

## 自動化キーワード判定
Hunter 検出「自動化キーワード含む: あり」は誤検出。タイトル/要素に自動化語は無く、逐次配信・自動収集・要約の機能記述でもない。検出は「アプリ/ツール」カテゴリの HN 高スコア発火のみ。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
スクレイピング対象データ/API/DS/エクスポートが全て無く、Kensho の Python スクレイピング資産で取得できる独占データがゼロ。可視化の再実装は 800GB データ + 9 ステップビルド + 精巧なUX が必要で既存競合 OneZoom が無料で同領域を満たす。再現困難価値を積む対象なし。内容を「要約データ商品」にするのも全入力が公開オープンデータで誰でも再現できコモディティ。

### 2) ローンチ手順 — 不成立
Kensho の配置経路（データAPI / 自動化 / 自前FastAPI / Apify/RapidAPI）のいずれにも乗らない。配信対象のデータ集合が入手不能（エクスポート無し）で、入手したとしても買う市場が無い（分類データの再梱包は NCBI/OTT/GBIF 等の無料オープン API で代替可能）。

### 3) 集客 — 不成立
集客アセット（属性データ / CtoA / 既存トラフィック / 既存観客）ゼロ。HN score 89 は打ち上げの一時的注目であり、永続的な有料観客にならない。閲覧者は教育・博物館・生物ファン層で、Kensho の既存観客（国内X懸賞応募/スクレイピング/Apify系）と重ならず、再配布先も無い。

## 結論
ptree.org は「アプリ/ツール」カテゴリの完全無料・パッション型教育可視化 Web アプリで、作者は ptable.com の製作者（1997年〜無料運営）。①公開データ API/DS/エクスポートが実測で全 404（JS 中の "api" はアナリティクスのみ） ②収益要素ゼロ（無料・寄付・有料版なし） ③全入力が公開オープン分類データでコモディティ（競合 OneZoom が無料で同領域） ④Kensho Python 資産の再利用対象なし ⑤集客観客の重なりゼロ。Apify/RapidAPI 以外のどの手法でも Kensho の収益商品に構成できないため、worker 実装タスクへの切り出しは行わない。

## verification_evidence
対象タスク: t_456b2ffa（実測コマンド出力の引用）

- site root / robots / sitemap 取得:
```
$ curl -sS -m 20 -A "Mozilla/5.0" https://ptree.org/
HTTP 200 size 165836 (index.html, title "Interactive Phylo Tree of Life - Ptree")
robots.txt: Cloudflare content-signal (search=yes, ai-train=no, use=reference; Allow: /)
sitemap.xml: HTTP 404
```

- データ/API/エクスポート端点を実測（全て 404、公開データアクセスなし）:
```
$ curl -o /dev/null -w "%{http_code}" https://ptree.org/api     -> 404
$ curl -o /dev/null -w "%{http_code}" https://ptree.org/data.json -> 404
$ curl -o /dev/null -w "%{http_code}" https://ptree.org/download  -> 404
$ curl -o /dev/null -w "%{http_code}" https://ptree.org/rss.xml   -> 404
$ curl -o /dev/null -w "%{http_code}" https://ptree.org/about     -> 301
```

- JS バンドル中の "api" 参照はアナリティクスのみ（ページロード時 plausible pageview 送信、bespoke データAPI ではない）:
```
$ grep -oE '.{25}api.{25}' /tmp/clade-Csauk_L2.js
...apiHost:"https://plausible.i ...o.open("POST",`${t.apiHost}/api/event`
Pageview:t}=je({domain:e,apiHost:`${location.origin}/
```

- ページ収益キーワード実測（価格/有料/寄付/サインイン/ダウンロード/ライセンスの記載なし）:
```
$ grep -inE "price|subscri|premium|donate|sponsor|paid|paywall|sign *in|download|license" ptree_root.html
なし（該当文字列は og: メタと CSS のみ）
```

- HN スレッド実測（score 89、コメント ~23、競合 OneZoom と公開オープンデータ由来を確認）:
```
$ curl -s -m 25 -A "Mozilla/5.0" "https://news.ycombinator.com/item?id=49559069"
score_49559069">89
commtext 約23件: "OneZoom[0] ... based on phylogenetic data sourced from Open Tree of Life"
              "This is vernacular picked up from Wikimedia commons ... WikiData"
              "Made by the creator of ptable.com, ... since 1997"
```

## 検出パイプラインへの推奨除外ルール
- カテゴリ「アプリ/ツール」かつ対象が 完全無料の教育/可視化 Web アプリ（サインイン・価格・有料版・エクスポート・API・DS なし）で、バックエンドデータが公開オープンソース由来（Wikipedia/Wikidata/NCBI/OTL 等）の場合、自動的に却下。
- 全データ入力がオープン公開の分野（分類学・地理・公共統計等）で、既存の無料オープン主力が存在する場合（例: 分類データ = NCBI/GBIF/Open Tree of Life + OneZoom）は、工数の重い「アグリゲーション/キュレーション」だけではコモディティで却下。
- 作者が長年無料で運営している親アプリ（ptable.com パターン）を持つ、即ち有料転換の意図が薄い制作者の場合は却下材料に加算。
