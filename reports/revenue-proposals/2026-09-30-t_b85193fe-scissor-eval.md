# 評価レポート: Show HN: Free alternative to graphics design giants (Scissor)

- Task: t_b85193fe
- 対象: https://scissor.studio/ / HN: https://news.ycombinator.com/item?id=49875308 (score 137, コメント 50)
- 元記事URL: https://scissor.studio/
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（非収益・実装対象外）**
- 実装工数推定: 適用外（実装すべき収益商品なし）

## 対象の実態
**Scissor** = Rust → WebAssembly のブラウザ内ベクター/ラスター画像エディタ（PWA、静的 SPA を Cloudflare で配信）。「Illustrator 等の有料巨大ツールの無料代替」を明言する**完全無料・サーバーレス製品**。
- root HTML 自体に収益方針を明記: "completely free, with no account, no sign-up and no subscription. Everything runs in your browser."（＝課金・アカウント・サブスクを最初から持たない設計）。
- manual/privacy に "no server behind it"。送信されるのは Google Analytics の訪問数のみ（オプトアウト可）。**ユーザーのアートワークも操作データも一切上がらない＝スクレイピング可能なデータレイヤ自体が存在しない**。
- 課金導線ゼロ: `/pricing` `/donate` `/buy` `/checkout` `/store` `/api` `/download` `/blog` はいずれも HTTP 200 だが返体は root と同一の SPA シェル（15251 bytes、差分は Cloudflare ビーコン 1 行のみ）＝**実ページ不在**。
- JS バンドル（`assets/main-*.js`、432444 bytes）全文走査: stripe / gumroad / patreon / ko-fi / paypal / paddle / lemonsqueezy / subscription / pricing / donate / checkout の**ヒット 0**。外部ホストは `github.com` と `googletagmanager.com` の 2 つだけ（決済・ストア・寄付先ゼロ）。
- ソース非公開: HN コメントが案内する `github.com/samalstudios/scissor-community` は issues/README/LICENSE のみで 200、`github.com/samalstudios/scissor` は **404**。org の公開リポジトリは scissor-community / homebrew-tap / posteci / jsglobe / kelane で **scissor 本体のソースは無い**（＝OSSとして fork/再配布して商品化する経路も無い）。
- 収集可能なデータなし: sitemap.xml は top + manual 26 ページの**他人製品のドキュメント**（27 URL）。`/rss` `/feed` は SPA シェルへフォールバック（購読エンドポイントなし）。robots.txt は GPTBot/ClaudeBot/PerplexityBot 等の AI クローラを明示歓迎（`Allow: /`, `Disallow: /alpha/` のみ）＝**crawl は自由だが取る価値のある生データが無い**。
- HN コメント（作者本人）: 「advanced app が値に見合わない層向けに作っている（can't afford to give an arm and a leg）」＝**想定ユーザー自身が価格感度が高い**。課金・寄付・有料版への言及はスレッド全体でゼロ（話題はバグ報告・機能要望・作り方の質問のみ）。
- 競合は無料で飽和: HN コメントに「photopea + inkscape で無料の編集ニーズは概ね足りる」と明言（photopea.com / inkscape.org とも 200 実測）。

## 自動化キーワード判定
Hunter フラグ「自動化キーワード含有: なし」で正しい。manual に `Automation`（Actions / Variables / Scripts）ページが存在するが、これは**製品内部のローカル機能**（"None of them needs an account or a server"）であり、Kensho の「自動収集・自動配信で売れるデータ」機能ではない。サーバーが無いため Kensho 側から叩ける自動化面（API / webhook / 定期配信データ）も存在しない。スキルの除外カテゴリ「開発ツール/製品内部機能の記述」に相当。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
- 本体の再実装は「Rust→WASM のフル画像エディタ」＝**製品そのもの**。作者がサンプル 1 点に "manual labor takes so much time" と語る級の長期工数で、24h worker の prototyping 対象ではない。そもそも同製品は**無料配布**なので、同品質を作れても売れる場所が無い。
- Kensho の再利用可能資産（Python スクレイピング + LLM 要約）の**入力データが存在しない**（サーバーレス / RSS・API・DS 皆無、あるのは他製品マニュアル 27 ページ）。マニュアルの二次利用は他人ドキュメントの転載でコモディティかつ価値・需要ともゼロ。
- 「無料エディタ向けテンプレート/スクリプト/素材パック販売」も不成立: Scissor は投稿から数日の新製品で利用者基盤が微小、かつ Variables / Export Data Sets / Scripts が**製品内蔵で無料完結**しており「バッチ生成ツール」は既に無料で存在する。素材販売自体も Creative Fabrica / Etsy / 無料 SVG サイトで飽和、Kensho にデザイナー向け生産パイプラインも観客も無い。
- 競合の無料代替（photopea / inkscape）が HN 上で複数名に挙がっており、新規 prototyping の差別化余地なし。

### 2) ローンチ手順 — 不成立
- Kensho の配置経路（自前 FastAPI データAPI / 自動化 cron / Gumroad デジタル商品 ※Apify・RapidAPI は本タスクの対象外）のどれにも載らない。データAPIは**データが無い**、Gumroad 商品は「無料の本体より価値のある有料品」を別途作る必要があり、それは元タスク（本製品の実装）とは別の事業＝本タスクのスコープ外。
- 収益導線が**原サイトにすら存在しない**（pricing/donate/checkout 等すべて実ページなし、JS バンドルに決済キーワード 0）。課金・寄付の受け口自体が無いため「この傍らで取る」材料が無い。
- 配置経路のうち唯一現実的な Gumroad 素材販売は、販売先の属性（デザイナー）が Kensho の既存販路（日本の懸賞 X アカウント）と重ならず、コンテンツ長期事業＝受動収益に非適合（スキルの却下パターン一致）。

### 3) 集客 — 不成立
- Kensho の集客アセット（属性データ / CtoA / 既存トラフィック / 既存観客）**ゼロ**。既存 X アカウントは日本の懸賞アカウントで、グラフィックツール利用者と重ならない。比較 SEO・アフィリエイト用のサイト/ドメイン/被リンクも持っていない（ゼロから建築するコンテンツ事業は受動収益に非適合）。
- HN score 137 / コメント 50 は十分な注目だが、**その流入はすべて scissor.studio 本体に吸われる**（Show HN の目的そのもの）。傍流で拾えるのは「作者への感想・要望」だけで、購買意向シグナルはゼロ。
- 加えて想定ユーザーが価格感度の高い層（本人発言）であり、無料の先行者（photopea / inkscape / Figma 等）で飽和した市場。

## 結論
Scissor.studio は **課金導線ゼロ・サーバーレス・ソース非公開の完全無料ツール**であり、Kensho の「スクレイピング + LLM 要約 → データ商品/販売ツール」型非API収益に転換可能な構成要素（収集データ / 課金面 / 集客面）が**一つもない**。スキル判定パターン「無料配布ツール: 収集データ・有料化余地なし → 却下」＋「公開ドキュメントの集約はコモディティ」＋「手動・長期のコンテンツ事業は受動収益に非適合」に一致。

- 成立条件を満たさないため、プロトタイプ/ローンチ手順/集客の3点はいずれも着手しない（24h 以内着手の要件は「実装可能な場合」に限られるため不成立）。

## 検出パイプラインへの推奨除外/優先ルール
- 「**サーバーレスのフロントエンド製品**（エディタ・ツール・ゲーム、データを一切持たない）」は、①課金/寄付系パスが全て SPA シェルにフォールバック、②JS バンドルに決済キーワードなし、③Sitemap がドキュメントのみ、の3点が揃えば**サーバーレス製品判定で即却下**（収集面と課金面が同時に無いため）。
- 「without subscription / free alternative」等、**無料であることを売りにする製品**は、傍収益（素材販売・比較 SEO）に展開しても本体ユーザーの価格感度がそのまま転移するため優先度を下げる。
- HN コメントで複数名が**無料の先行代替**（photopea / inkscape 等）を並挙しているものは市場飽和の直接証拠として拾う。
- 「github.com/<org>/<product> が 404 で issues リポジトリのみ」の製品は OSS fork 経路も無いため、再実装コスト＝全额自己負担と判定する。

## 元データ
- scissor.studio root 200 / 15251 bytes、SPA（`assets/main-*.js` 432444 bytes + `scissor_bg-*.wasm` + manifest.webmanifest）
- root 記載: "completely free, with no account, no sign-up and no subscription"、privacy: "no server behind it"
- robots.txt 200（全クローラ歓迎 / `/alpha/` のみ除外）/ sitemap.xml 200（27 URL = top + manual 26）
- `/pricing` `/donate` `/buy` `/checkout` `/store` `/api` `/download` `/blog` → 200 だが全て root と同一シェル（差分は CF ビーコン 1 行）
- JS バンドル決済キーワード 0 ヒット、外部ホスト `github.com` / `googletagmanager.com` のみ
- HN item 49875308: 137 points / 50 comments（HTML 直読みと Algolia API の二重確認）
- github.com/samalstudios/scissor → 404、scissor-community → 200（issues のみ）、org 公開リポジトリは scissor 本体なし
- 競合 200: photopea.com、inkscape.org
- HN コメント: 作者「can't afford to give an arm and a leg」＝価格感度層を想定 / 課金・寄付への言及ゼロ

## verification_evidence
検証コマンド(2026-09-30 実測, task t_b85193fe):

$ grep -oE '[0-9]+ points|[0-9]+&nbsp;comments' hn_b85.html
137 points
50&nbsp;comments

$ curl -sS -m 15 "https://hn.algolia.com/api/v1/items/49875308" | grep -oE '"points":[0-9]+' | head -1
"points":137

$ for p in pricing donate buy checkout store api download blog; do curl -sS -m 15 -o /dev/null -w "/$p %{http_code} %{size_download}\n" "https://scissor.studio/$p"; done
/pricing 200 15251
/donate 200 15251
/buy 200 15251
/checkout 200 15251
/store 200 15251
/api 200 15251
/download 200 15251
/blog 200 15251

$ diff <(fold -w80 sc_root.html) <(fold -w80 sc_pricing.html) | sed -E 's/[0-9a-f]{12,}/<nonce>/g' | head -6
331c331
< w.__CF$cv$params={r:'<nonce>',t:'MTc5MDc1MTgzOQ=='};var a=document.crea
---
> w.__CF$cv$params={r:'<nonce>',t:'MTc5MDc1MTk0OA=='};var a=document.crea

$ grep -ciE 'stripe|gumroad|patreon|ko-fi|paypal|paddle|lemonsqueezy|subscription|pricing|donate|checkout' sc_main.js
0

$ grep -oE 'https://[a-z0-9.-]+' sc_main.js | sort | uniq -c
      1 https://github.com
      1 https://www.googletagmanager.com

$ grep -oE 'completely free, with no account[^"]*' sc_root.html
completely free, with no account, no sign-up and no subscription. Everything runs in your browser.

$ grep -ohiE 'no server behind it' privacy_page.html
no server behind it

$ grep -c '<loc>' sc_sitemap.xml.txt
27

$ grep -oE 'Disallow: /alpha/|User-agent: GPTBot' sc_robots.txt.txt | sort -u
Disallow: /alpha/
User-agent: GPTBot

$ curl -sS -m 20 -o /dev/null -L -w '%{http_code}\n' https://github.com/samalstudios/scissor
404

$ curl -sSL -m 20 -A 'Mozilla/5.0' "https://github.com/samalstudios?tab=repositories" -o gh_org.html -w 'code=%{http_code} bytes=%{size_download}\n'; grep -oE 'scissor-community|homebrew-tap|posteci|jsglobe|kelane' gh_org.html | sort -u
code=200 bytes=227178
homebrew-tap
jsglobe
kelane
posteci
scissor-community

$ for u in https://www.photopea.com/ https://inkscape.org/; do curl -sS -m 20 -o /dev/null -L -w "$u %{http_code}\n" "$u"; done
https://www.photopea.com/ 200
https://inkscape.org/ 200
