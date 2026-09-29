# 評価レポート: Show HN: HN.watch – Videos of all Hacker News posts

- Task: t_ce86cc7c
- 対象: https://hn.watch/ / HN: https://news.ycombinator.com/item?id=49879401 (score 193, コメント 96)
- 元記事URL: https://hn.watch/
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（非収益・実装対象外）**
- 実装工数推定: 適用外（実装すべき収益商品なし）

## 対象の実態
**HN.watch** = Scrimba（YC S20, オスロ）が自社製品「Scrimba Explain」のデモとして公開した「HN フロントページの各記事を初回クリック時に LLM で解説動画生成する」プロモーションサイト。
- サーバサイド静的な HN フロントページ複製（`/?item=<id>` 形式の全項目リンク、2ページ目まで）。動画は Scrimba の HTML ベース動画プレイヤーを iframe で埋め込み（`scrimba:embed-*` メッセージ受信部あり）。
- フッター明記: "scrimba explain · not affiliated with y combinator"。全ページから `scrimba.com/explain?via=hn_watch` への導線のみ＝**収益導線ではなく集客ファネル**。`/pricing` `/subscribe` `/api` はいずれも **404**（課金・購読・API ゼロ）。
- データ出所は公開 HN（フロントページ HTML および公開 Algolia API、`hn.algolia.com/api/v1/items/49879401` → 200 / 50929 bytes）。**独占データは一切無い**。
- 運営者の HN コメントでコスト開示: 「We currently spend ~$0.4 on a video (without images) and have a few seconds of delay before playback」、MCP 経由の生成は「It's currently free ... we cover the TTS for the time being」＝**現状無料・原価は1本あたり約0.4ドル**。
- robots.txt は `User-agent: * / Allow: /` のみ（スクレイピング自体は許可）だが、sitemap.xml / rss / feed / index.xml / api はすべて 404。**配信・購読エンドポイントが存在しない**。

## 自動化キーワード判定
Hunter フラグ「自動化ワード含む: あり」＝**誤検出**。本件の自動化は「初回クリック時にその場で動画を生成する（on-the-fly generation）」という**デモ自体の機能記述**であり、Kensho の「自動収集・自動配信で売れるデータ」機能ではない。スキルの除外カテゴリ「開発ツール/デモ内部機能の記述」に相当。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
再利用可能な Kensho 資産（Python スクレイピング + LLM 要約）で作れる**のは「HN 要約コンテンツ」だけ**で、それすらコモディティ。
- 入力データは公開 HN API / フロントページ由来で誰でも取得可能（Algolia 200 実測）。**独占性・再現困難性ゼロ**。
- 本命となる「解説動画」は Kensho の資産外。TTS + スクリーン/アニメーション合成 + ffmpeg + CDN + LLM 原稿生成のインフラ整備が必須で、かつ原価がかかる（原作の実測 0.4 ドル/本 ≒ 12〜16 円/本、フロント30件/日で約 400〜500 円/日 ≒ 月 1.2〜1.5 万円）。**月1〜3万円の目標売上に対し原価だけで目標に迫る**。
- 同種の実装は OSS として既に存在（`scosman/videowright` 200 実測: ボイスオーバー整合・ElevenLabs・MP4 出力・再編集まで実装済み）。**新規 prototyping の差別化余地が無い**。
- 「LLM 要約テキスト/音声だけ」に絞った場合も、HN 公開データ集約 + LLM 要約 = 誰でも再現可能のコモディティ（スキルの却下パターンに直撃）。

### 2) ローンチ手順 — 不成立
- Kensho の配置経路（自前 FastAPI データAPI / 自動化 / Gumroad デジタル商品 / Apify・RapidAPI ※本タスクでは対象外）のどれにも乗らない。**動画生成・配信はどれも「データ商品/販売ツール」前提の経路に載せられない**。
- 課金導線が原サイトにすら存在しない（pricing/subscribe/api 404）。「解説動画を売る」場合の競合は、まず**無料の Scrimba 本体**（YC S20 ブランド + HN フロントページ級の流入 + TTS 負担中）。
- 動画/Podcast の定期配信は、配信先（RSS → YouTube / Spotify / iHeart）登登録・毎日回し続ける運用工事であり、**受動収益に非適合の手動長期事業**。

### 3) 集客 — 不成立
- Kensho の集客アセット（属性データ / CtoA / 既存トラフィック / 既存観客）**ゼロ**。既存の X アカウントは日本の懸賞アカウントで、HN・プログラミング学習動画の視聴者と重ならない。
- 元 HN は score 193 / コメント 96 と高注目だが、**その流入は Scrimba の無料デモに吸われる**（まさに元記事の目的）。コメント欄の需要シグナルは「音声だけのフィードが欲しい」「ポッドキャスト化してほしい」等で、**いずれも無料で提供される方向の要望**。課金意向の発言はゼロ、運営側の発言は採用告知とコスト最適化のみ。
- 競合が既に飽和: 無料 HN ポッドキャスト/ダイジェストが複数稼働（`bri.so/show/hackernews/en`、Hacker News Daily YouTube/iHeart/Spotify、`audioreality.ai` のメール配信日次ポッドキャスト、OSS `ykdojo/hacker-news-digest` — すべて 200 到達実測）。加えて HN コメント内で `Editory`（ローカルニュース動画化）の先行例も指摘済み。

## 結論
HN.watch は **Scrimba Explain の営業デモ（課金ゼロ・導線は scrimba.com/explain のみ）**であり、データは公開 HN 由来で独占性ゼロ、動画生成は Kensho の資産外かつ原価が目標売上級、無料の先行者（Scrimba 本体 + 無料ポッドキャスト群 + OSS）で飽和、集客アセットはゼロ。Kensho の「スクレイピング + LLM 要約 → データ商品/販売ツール」型非API収益に転換可能な構成要素が一つもない。スキル判定パターン「ニュースアグリゲータ/キュレーション: 生情報は公開ソース由来で独自価値なし → 却下」＋「公開ソースの集約+LLM要約はコモディティ」＋「手動の長期事業は受動収益に非適合」に一致。

- 成立条件を満たさないため、プロトタイプ/ローンチ手順/集客の3点はいずれも着手しない（24h以内着手の要件は「実装可能な場合」に限られるため不成立）。

## 検出パイプラインへの推奨除外/優先ルール
- 「HN（または他掲示板）の全投稿を自動生成コンテンツ化するデモ系 Show HN」は、①入力が公開 API 由来、②配信エンドポイント（rss/pricing/subscribe/api）が全て 404、③外部 SaaS への導線リンクのみ、の3点が揃えば**営業デモ判定で即却下**。
- 「on-the-fly / auto-generate / realtime でその場で作る」系の自動化ワードは、生成デモの機能記述＝誤検出として除外（収集・配信機能と混同しない）。
- 運営者がコメントで「原価 $X/本」「現時点では無料」と開示しているものは、価格戦略の余地が無いため優先度を下げる。

## 元データ
- hn.watch root 200 / 47043 bytes、`<title>HN.watch | Hacker News with explainer videos</title>`
- robots.txt 200（`User-agent: *` `Allow: /` のみ）/ sitemap.xml 404 / rss 404 / pricing 404 / subscribe 404 / api 404
- フッター導線 `scrimba.com/explain?via=hn_watch`（唯一の外部導線）
- HN item 49879401: 193 points / 96 comments（46 本文パース）
- hn.algolia.com/api/v1/items/49879401 → 200 / 50929 bytes（公開データ出所）
- 競合 200: github.com/ykdojo/hacker-news-digest、github.com/scosman/videowright、bri.so/show/hackernews/en

## verification_evidence
検証コマンド(2026-09-29 実測, task t_ce86cc7c):

$ curl -sS -m 20 -o root2.html -w 'code=%{http_code} bytes=%{size_download}\n' https://hn.watch/
code=200 bytes=47043

$ grep -oE '<title>[^<]*</title>' root2.html
<title>HN.watch | Hacker News with explainer videos</title>

$ for p in robots.txt sitemap.xml rss pricing subscribe api; do curl -sS -m 15 -o /dev/null -w "/$p %{http_code}\n" "https://hn.watch/$p"; done
/robots.txt 200
/sitemap.xml 404
/rss 404
/pricing 404
/subscribe 404
/api 404

$ grep -o 'scrimba.com/explain?via=hn_watch' root2.html | sort -u
scrimba.com/explain?via=hn_watch

$ grep -oE 'We currently spend[^<]{0,60}|currently free[^<]{0,60}' hn_thread.html | sort -u
We currently spend ~$0.4 on a video (without images) and a have a few seconds of delay before playback.
currently free, as the tokens for directing and scripting it is offloaded to your agent. And then we cover the TTS for the time being.

$ grep -oE '193 points|[0-9]+&nbsp;comments' hn_thread.html | sort -u
193 points
96&nbsp;comments

$ curl -sS -m 15 -o alg2.json -w 'algolia code=%{http_code} bytes=%{size_download}\n' https://hn.algolia.com/api/v1/items/49879401
algolia code=200 bytes=50929

$ for u in https://github.com/ykdojo/hacker-news-digest https://github.com/scosman/videowright https://bri.so/show/hackernews/en; do curl -sS -m 15 -o /dev/null -L -A 'Mozilla/5.0' -w "$u %{http_code}\n" "$u"; done
https://github.com/ykdojo/hacker-news-digest 200
https://github.com/scosman/videowright 200
https://bri.so/show/hackernews/en 200
