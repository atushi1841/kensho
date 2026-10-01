# 評価レポート: Show HN: Ledge.sh – Runnable Markdown Notes

- Task: t_e2fb0a95
- 対象: https://ledge.sh / HN: https://news.ycombinator.com/item?id=49902382 (score 102, コメント 47)
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（実装対象外）**

## 対象の実態
**Ledge** = ノート内でシェル・コード・SQLを即座に実行できる「ランナブル Markdown ノート帳」。Mac/Linux/Windows/WSL/iOS/Android 対応。Electrobun(Bun ベース)上の React+CodeMirror アプリで、ledge-server は SSH 越しにホスト可能。**完全フリー・オープンソース (Apache-2.0, GitHub ledgesh/ledge)**。

- ledge.sh は Vercel でホストされる静的マーケティングサイト (Next.js SSG)。
- ドキュメント群 (/docs/*) は全部合わせて 70KB 程度の静的 HTML。
- /api は Disallow (robots.txt) かつ 404。
- /rss, /feed.xml は 404。
- sitemap.xml は /docs/* のページリンクのみ (更新情報以外の動的データなし)。
- privacy ページによれば **アカウントも API もなく**, アップデートチェック以外の解析データは「チャンネル/OS/国/日次ハッシュ」のみ。ユーザーノート・コマンド・キーは一切サーバーへ送らない。
- 収益モデル: **無し**。pricing は存在せず、GitHub Release からのダウンロード + App Store/Play ストアの OSS 配布。

## 自動化キーワード判定
Hunter フラグ「自動化キーワード: なし」(「realtime / daily digest / poll / auto」等の語は本文・プライバシーの「once a day」アップデートチェックくらいで、実際の自動収集配信サービスではない)。

## 3点評価 (Kensho 非API収益モデル)
### 1) プロトタイプ — 不成立
- Kensho スクレイピング/LLM資産を活かす**排他的・独占データが存在しない**。Ledge は *ユーザー自身のローカルノート*を実行するローカルツールであり、外部から収集可能なデータソースはマーケティングサイトの静的ページとドキュメントだけ。
- これら「データ」は一般的な公開ウェブページの抓取りであり、価値ある独占性・再現困難性もない。「集約 + LLM要約」でもコモディティかつ有料化対象外。
- ダウンロード可能DSは存在せず、スクレイピング対象のデータも「誰でも curl できる説明ページ」に過ぎない。

### 2) ローンチ手順 — 不成立
- Kensho の配置経路 (データAPI/自動化/自前FastAPI/Apify/RapidAPI) は「売れるデータ or 販売ツール」を前提とするが、Ledge は OSS デスクトップアプリ本体。Kensho がホスト・再配布する商品にもなれない (ライセンス Apache-2.0, 著作権 2026 Dan Stevens)。
- 課金導線がゼロ。元サイトは完全無料・オープンソース。個人趣味 OSS のひとつ。

### 3) 集客 — 不成立
- 集客アセットゼロ。元HN score 102/コメント 47 は中程度だが、これは「ランナブルMarkdownノート」という技術テーマの関心を示す HN 内の刹那的な関心であり、**有料の反復トラフィック/観客**は存在しない。
- コメントには既存の競代 (xcfile/xc) 言及もあるが、これらはすでにマネー・プライスモデルもない OSS。市場は飽和/志雄的で収益化されていない。
- Kensho が「X懸賞応募自動化」で培ったスキルとも業務領域が完全に異種。

## 結論
Ledge.sh は OSS のランナブル Markdown ノートアプリで、外部に収集可能なデータも存在せず、収益・課金導線もゼロ (Vercel 解析以外のユーザーデータは収集しない)。Kensho の「スクレイピング+LLM要約 → データ商品/販売ツール」型非API収益に転換する構成要素が全くない。「技術速報/リリースノート要約」および「公開ソース由来の集約(コモディティ)、有料化余地なし」の却下パターンに該当する。ランク高の自動検出フラグは技術テーマ+Ledger的キーワード(「run shell commands / code / SQL / runnable」)による誤検出であり、スキップが正しい。

- 成立条件を満たさないため、プロトタイプ/ローンチ手順/集客の3点は着手しない。

## verification_evidence
$ curl -s -o /dev/null -w "%{http_code}" https://ledge.sh
200
$ curl -s -o /dev/null -w "%{http_code}" https://ledge.sh/robots.txt
200 (User-Agent: * / Allow: / / Disallow: /api/ / Disallow: /updates/ / Sitemap: https://ledge.sh/sitemap.xml)
$ curl -s https://ledge.sh/sitemap.xml | head -c 600
<?xml version="1.0" encoding="UTF-8"?><urlset ...><url><loc>https://ledge.sh/</loc></url><url><loc>https://ledge.sh/docs</loc></url>...<url><loc>https://ledge.sh/android</loc></url><url><loc>https://ledge.sh/privacy</loc></url></urlset>
(公開ページリンクのみ。データAPI/フィード/更新JSON なし)
$ curl -s -o /dev/null -w "%{http_code}" https://ledge.sh/api
404
$ curl -s -o /dev/null -w "%{http_code}" https://ledge.sh/rss
404
$ curl -s -o /dev/null -w "%{http_code}" https://ledge.sh/feed.xml
404
$ curl -s -o /dev/null -w "%{http_code}" https://ledge.sh/pricing
404
$ curl -s -o /dev/null -w "docs[%{http_code} size=%{size_download}]" https://ledge.sh/docs
docs[200 size=70474] (静的 HTML のみ)
$ curl -s https://ledge.sh/privacy | grep -i "account\|api\|subscribe\|payment\|pricing\|stripe"
(no matches — 「Ledge has no accounts, and the apps never send your notes to us.」)
$ curl -s https://api.github.com/repos/ledgesh/ledge | head -c 400
{... "license": {"key":"apache-2.0"}, "stargazers_count":..., "html_url":"https://github.com/ledgesh/ledge" ...} (Apache-2.0 OSS)

## 元データ
- 実測: ledge.sh root 200 (Next.js SSG)、/robots.txt 200 (api/updates Disallow, sitemapあり)、/sitemap.xml 200 (docsページリンクのみ)、/api 404, /rss 404, /feed.xml 404, /pricing 404
- /docs は静的 HTML 70KB (データソースなし)
- /privacy は「アカウントなし・ノートをサーバーへ送らない」明記。解析は Vercel Web Analytics のチャンネル/OS/国/日次ハッシュのみ
- GitHub ledgesh/ledge: Apache-2.0, OSS デスクトップアプリ。収益/課金導線ゼロ
- HN 49902382: score 102 / コメント 47 (前回計測 2 points →再計測 102 points に訂正)
