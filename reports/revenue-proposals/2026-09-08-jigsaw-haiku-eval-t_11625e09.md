# 評価レポート: Show HN: Jigsaw Haiku (t_11625e09)

- Task: t_11625e09
- 対象: https://jigsawhaiku.com/ / HN: https://news.ycombinator.com/item?id=49568162 (score 82 / コメント 27、2026-09-04 投稿)
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（非収益・実装対象外・第三者の創作物を配信する静的無料ゲーム）**
- 実装工数推定: 適用外（実装すべき収益商品なし）

## 対象の実態
**Jigsaw Haiku** = 「1日1題、手書きの俳句をジグソーで組み立てる」静的 Web ゲーム。作者本人が HN に「just a static react app hosted on Render, no backend」と明記。俳句は作者が手書き（AI に素材リスト生成を併用）、背景アートは Gemini/ChatGPT 生成。姉妹サイト The Daily Baffle（dailybaffle.com）への導線のみ。課金・広告・API 提供・ログインは一切なし。

## 自動化キーワード判定
Hunter の自動化ワードは「daily（毎日のパズル配信）」由来と推定。これは**コンテンツ更新頻度の記述であり、自動収集・自動配信機能の記述＝誤検出**（スキルの既知パターンどおり）。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
唯一の「構造化データ」である JSON フィードの中身は、**作者の創作物（手書き俳句＋AIアート）そのもの**。
- 転載・転売は著作権侵害であり、Kensho モデル（公開**事実データ**の集約→データ商品）の前提を最初から満たさない。価格・スケジュール・求人等の事実データと異なり、この俳句集合には事実データの集約価値がない。
- 独自性を捨てて「LLM で毎日俳句＋アート生成」を自前でやっても、数秒で誰でも再現できるコモディティ。HN スレッドに「俳句データセットが欲しい」需要シグナルは皆無で、販売先が存在しない。
- Kensho 資産（Python スクレイピング＋LLM 要約、懸賞自動化）と接続できる要素がない。

### 2) ローンチ手順 — 不成立
Kensho の配置経路（データAPI / 自動化 / 自前FastAPI / Apify / RapidAPI）はいずれも「売れるデータ or ツール」前提。本件は (a) 他者創作物なので法的に商品化不可、(b) 自前生成版はコモディティ、(c) 同型の無料パズルサイト運営は集客ゼロからの長期手動事業で受動収益に非適合。

### 3) 集客 — 不成立
- 集客アセット（属性データ / CtoA / 既存トラフィック / 既存観客）はゼロ。姉妹サイト Daily Baffle への導線はあるが、それは作者の観客であって Kensho のものではない。
- 原 HN score 82 と注目度は高いが、集まった観客は「パズルプレイヤー」であり、Kensho の既存観客（懸賞応募層・スクレイパー/データバイヤー）と重複しない。

## 結論
Jigsaw Haiku は「バックエンドなしの静的無料ゲーム」で、公開 JSON フィードを持つ点は一見データ収集候補に見えるが、その中身は**作者の創作物（俳句＋アート）＝転売法的に不可・自前生成はコモディティ・需要シグナルゼロ**。NYC MapTap（t_bd5de3ff）と同じ「静的無料アプリ」却下パターンの変種（データ同梱 → データ公開配信）として却下。プロトタイプ/ローンチ/集客の3点はいずれも着手対象外。

## 検出パイプラインへの推奨除外/優先ルール
- 「Daily puzzle / daily quiz / 毎日更新ゲーム」系の **daily ワードは更新頻度の記述＝誤検出**として自動除外対象に。
- 公開 JSON/RSS フィードが存在しても、**コンテンツが作者の創作物（詩・絵・写真・ストーリー）の場合はデータ商品化不可**（著作権）→ 即却下。データ候補として扱うのは公開事実データ（価格・在庫・スケジュール・公募・リスティング）のみ。
- ゲーム/パズル系 HN は「体験」が価値であり、HN スコアが高くても（本件 82）データ需要・課金シグナルの有無をコメント実査で確認してから上位採択すべき。

## verification_evidence

以下、t_11625e09（Jigsaw Haiku）評価の実測コマンド出力。jigsawhaiku.com の HTTP ステータスを直接 curl で検証（2026-09-08 実測）。

```bash
$ curl -sS -o /dev/null -w 'root: %{http_code} %{size_download}\n' --max-time 20 https://jigsawhaiku.com/
root: 200 1619

$ curl -sS -o /dev/null -w 'puzzle_20260908: %{http_code}\n' --max-time 20 https://jigsawhaiku.com/puzzles/2026-09-08.json
puzzle_20260908: 200

$ curl -sS -o /dev/null -w 'robots: %{http_code}\n' --max-time 20 https://jigsawhaiku.com/robots.txt
robots: 404

$ curl -sS -o /dev/null -w 'sitemap: %{http_code}\n' --max-time 20 https://jigsawhaiku.com/sitemap.xml
sitemap: 404

$ curl -sS -o /dev/null -w 'rss: %{http_code}\n' --max-time 20 https://jigsawhaiku.com/rss
rss: 404

$ curl -sS -o /dev/null -w 'feed: %{http_code}\n' --max-time 20 https://jigsawhaiku.com/feed
feed: 404
```

```
root: 200 1619
puzzle_20260908: 200
robots: 404
sitemap: 404
```
