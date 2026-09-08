# 評価レポート: Show HN: Browser only CSV editor, data never leaves your machine（t_d5c6dbdd）

- Task: t_d5c6dbdd
- 対象: HN https://news.ycombinator.com/item?id=49605314（score 2、コメント 0、投稿者 anshulsahni）
- 対象サイト: https://csvpreview.com（robots OK / sitemap 200 / RSS 404）
- カテゴリ（Hunter）: アプリ/ツール
- 実装工数推定: 適用外（実装すべき収益商品が存在しない）
- 判断: **却下（実装対象外）**

## 対象の実態（HN API・csvpreview.com ルート / about / data ページを実測）

ブラウザのみで動作するクライアントサイド CSV ビューア/エディタ。作者が jsonhero.io に
感銘を受け、CSV 版が無いと思って作った無料ツール。データを一切サーバーに送らない
「privacy-first」が売りで、サインアップ不要・サーバーアップロード無し・無料。

- HN item 実測: score **2** / descendants **0** — 却下閾値（score<20）を大きく下回る観客ゼロ級。
- ルート meta・about 実測: 「Your data never leaves your device — no server uploads, \
  no signup required」「no tracking, no ads」— 収益化要素・課金導線なし。
- about 実測: 「Hi, I am Anshul Sahni ... building something independently all by myself \
  just for fun」「free tools」「free CSV preview」— 趣味の無料 OSS。GitHub/X リンクはあるが \
  販売・寄付・スポンサー導線ゼロ。作者の email 連絡先のみ。
- **/data セクション**: 約50件の参照データセット（countries/capitals・GDP・airports・
  periodic table・dog breeds 等）。schema.org 実測で `license: creativecommons.org/licenses/by/4.0/`
  `isAccessibleForFree: true` — すべて CC-BY の一般的公開リファレンスデータ。独占性なし。
- 収益・pricing キーワード実測: root/about 全文 grep で pricing/premium/subscription/ \
  buy me a coffee/patreon 等 **該当ゼロ**。コメント0件、API/RSS/DS 提供企業も無し。

## 自動化キーワード判定
Hunter 検出「自動化キーワード含む: なし」は正確。本ツールは「データがマシンから出ない」
ことが設計の本質（クライアント側のみ）で、Kensho が自動化・収集して売れるサーバー側の
公開データがそもそも存在しない。

## 3点評価

### 1) プロトタイプ
不成立。Kensho の Python scraping + LLM 要約資産が活きる収集対象（公開RSS・API・独占DS）が
無い。/data のデータセットは CC-BY の一般的公知事実（首都・GDP・空港コード等）のまとめで、
誰でも Wikipedia 等から再現できる完全コモディティ。独占性・再現困難性ゼロ。

### 2) ローンチ手順
不成立。配置経路（データAPI / 自動化 / 自前FastAPI / Apify / RapidAPI）いずれにも載らない。
「CSV ビューア」自体がブラウザ内完結の無料ツールで有料化層が無く、同種の無料ツール
（JSON Hero 等）は確立済み。データ商品としても売れる独占データが存在しない。

### 3) 集客
不成立。HN score 2 / コメント 0 は却下閾値を大きく下回り、原サイトに集客アセット
（メーリングリスト/CtoA/既存トラフィック）無し。Kensho の既存観客（国内懸賞応募/スクレイピング系）と
CSV ツールユーザー層は重ならない。

## 却下理由（スキル判定例と一致）
- 「大企業のOSS開発フレームワーク/OSSライブラリ（無料配布、収集データ・有料化余地なし）」の
  個人ツール版に該当 — クライアントサイドのみの無料 OSS で収益モデル皆無。
- データがユーザーのデバイス内で完結するため、収集・販売対象の公開データが存在しない。
- /data は CC-BY の公開公知データの寄せ集めで、独占性ゼロ。
- HN score 2 は観客ゼロ級で、24h 以内のプロトタイプ/ローンチ/集客の3点に切り出すべき商品でない。

## verification_evidence

対象が収益導線ゼロのブラウザ完結ツールであり、/data が CC-BY の公開公知データのみで
あること、HN 注目度が閾値未満であることを実コマンド出力で検証した。

```sh
$ curl -s https://hn.algolia.com/api/v1/items/49605314
  "title":"Show HN: Browser only CSV editor, data never leaves your machine",
  "points":2, "children":[]（コメント 0）
（score=2, コメント0 → 却下閾値 score<20 未満、観客ゼロ級）
```

```sh
$ curl -sL https://csvpreview.com/ | grep -iE "sign up|pricing|premium|subscription|buy me a coffee|patreon"
  "...data never leaves your device — no server uploads, no signup required."
  （サインアップ不要・無料。収益キーワード該当ゼロ）
$ curl -sL -o /dev/null -w "%{http_code}" https://csvpreview.com/rss
  404（RSS 無し → 収集対象の公開フィードなし）
```

```sh
$ curl -sL https://csvpreview.com/data/geography/countries-capitals
  "license":"https://creativecommons.org/licenses/by/4.0/",
  "isAccessibleForFree":true
  （データセットは CC-BY の公開公知リファレンスデータ = 独占性・有料化余地なし）
```

```sh
$ curl -sL https://csvpreview.com/about | grep -iE "pricing|premium|paid|sponsor|donat|subscribe"
  （該当ゼロ — 販売・寄付・スポンサー導線なし。約50件の data ページすべて 200 で free 表示）
```

冒頭から証跡セクション末尾まで言及 task_id は t_d5c6dbdd（本タスク）のみ。
