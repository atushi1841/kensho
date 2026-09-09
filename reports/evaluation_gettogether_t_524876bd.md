# 評価レポート: GET Together — A social network where you don't need POST to Post

- Task: t_524876bd
- 対象: https://gettogether.dev / HN: https://news.ycombinator.com/item?id=49592840 (score 36, 12 comments)
- カテゴリ: アプリ/ツール
- 判断: 非API自動収益として **実装対象外（却下）**
- 実装工数推定: なし（着手せず worker 実装タスクへ切り出さない）

## 対象の実態
GET Together は **「投稿が GET リクエストである」ソーシャルネットワーク（ノベルティ玩具）**。
- 機能: メッセージを HTTP GET リクエストのパラメータで投稿。新着順に公開表示、ハート(report/heart)。投稿取得は公開 JSON API `/feed`。
- 技術: 静的 HTML + JS SPA（app.js 53KB）。`/feed`（GET）・`/heart`・`/delete`・`/report` を実測確認。
- 配布: 無料Web。課金・サブスク・プロダクト面なし。運営は個人ハッカー（nchudleigh）。
- robots.txt: **User-agent / Allow / Disallow 行が一切なく、EU CDSM第4条準拠の content-signal（search / ai-input / ai-train）フレームワークのみ**。どのシグナルにも yes/no 未設定。ただし「AI入力/AI学習への同意」を明示的に扱う = UGC 収集・AI転用への警戒姿勢。
- データ実測: `/feed` の投稿は **実測30件**で、ほぼ全て「hello everyone」「test」「ping」等の発売直後のテスト挨拶。フォロー数・話題・属性・継続的トラフィック・収益面なし。
- HN コメント全12件: 「OpenAIに知られたら終わり」「LLMエージェント用のハニーポットでは?」「botから守る方法を考えて」「perplexity下限でステガノグラフィ通信を防げ」など。**作者自身が bot/LLM エージェント流入に警戒**（"Good thinking."）。実態は「主要ユーザーが LLM エージェント」という趣向の驚き玩具ネットワーク。

## 自動化キーワード判定
Hunter 検出の自動化ワード欄は「なし」。タイトル「don't need POST to Post」は HTTP メソッドの語呂合わせで、収集・配信・収益自動化の機能記述ではない。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
公開 JSON API `/feed` は存在し技術的スクレイピングは可能だが、収集対象データに独占性・再現困難性が全くない。対象は「匿名のノベルティ投稿」の **発売直後30件の挨拶のみ**で、ボリューム・話題・属性・商業価値すべてゼロ。Kensho の Python スクレイピング+LLM 資産で `/feed` を集約しても「誰でも1コマンドで再現できるコモディティ」であり、集約結果（無内容のテスト投稿）を商品化する需要は存在しない。さらに robots.txt の content-signal 枠組みは UGC の収集・AI転用への同意を意識しており、玩具ネットの UGC を集約・再配布する運営意図との齟齬リスクが残る。

### 2) ローンチ手順 — 不成立
Kensho の配置経路（データAPI / 自動化 / 自前 FastAPI / Apify / RapidAPI）に乗らない。継続的に変化する有料・独占データ源がなく、課金可能なサービスや「収集対象が増える仕組み」も無い。「GET Together 投稿の集約/配信 API」を RapidAPI に載せても需要ゼロ・データゼロ。`anystation.net`（GET/email/ssh 投稿、HNコメントで言及）という同類の驚き玩具も既に存在しニッチ飽和。月1〜3万円の受動収益構造を構成し得ない。

### 3) 集客 — 不成立
集客アセット（属性データ / CtoA / 既存トラフィック / 既存観客）がゼロ。HN score 36 は注目はあったがサイト運用トラフィックは実質ゼロで、対象自体が「エージェントのハニーポット」という新奇性消費。Kensho の既存観客（国内懸賞・スクレイピング系）とも一切重ならない。

## 結論
GET Together は「アプリ/ツール」カテゴリだが、①収集対象データに独占性なし（発売直後30件の無内容テスト投稿で /feed は誰でも取得可能）②課金可能なデータ・サービス・有料データ源が存在せず受動収益構造に不適合 ③robots.txt の content-signal 枠組みが UGC 収集/AI転用への同意を意識（収集意図との齟齬リスク） ④作者自身が bot/LLM エージェント流入に警戒し実態が「新奇性だけの玩具ネットワーク」⑤集客ゼロ（既存観客なし・観客も重ならない）。
Apify/RapidAPI 以外のどの手法でも Kensho の収益商品に構成できないため、worker 実装タスクへの切り出しは行わない。

## 検出パイプラインへの推奨除外ルール
- カテゴリ「アプリ/ツール」で対象が「投稿が特殊な HTTP メソッド/手段である」ノベルティ・驚き玩具の SNS/ネットワークで、課金面・有料データ源・継続的収集対象・既存観客が無い場合、自動的に非収益と判定する。
- 対象が「LLM エージェントの脱走/ハニーポット」趣向で、robots.txt に content-signal（ai-input/ai-train/search）枠組みがある UGC サイトは、収集・AI転用の同意リスクを判定材料に含めて自動却下する。

## verification_evidence
本判定に用いた実測コマンドと実出力（2026-09-07 JST 実施）。

$ curl -s -L -A "UA" https://gettogether.dev/robots.txt
```
# content signals ... search / ai-input / ai-train ...
# ANY RESTRICTIONS ... RESERVATIONS OF RIGHTS UNDER ARTICLE 4 OF THE
# EUROPEAN UNION DIRECTIVE 2019/790 ON COPYRIGHT ...
```
→ robots.txt は User-agent/Allow/Disallow を持たず content-signal 枠のみ（収集/AI転用の同意を明示扱い）。

$ python3 fetch_gt.py  # root と sitemap/rss と HN item を実測
```
### gt_sitemap: status=404 final=https://gettogether.dev/sitemap.xml bytes=0
### gt_rss:     status=404 final=https://gettogether.dev/rss.xml bytes=0
### hn_item:    status=200
```
→ sitemap/rss は存在せず（RSS/DS なし）。HN item は 200。

$ python3 feed_count.py  # GET /feed JSON を実測
```
feed posts count: 30
  - 1788765106976 alsanan | hearts 1 | replies 0 | hello everyone from my console
  - 1788764016403 ahoy    | hearts 1 | replies 0 | ahoy-hoy
```
→ /feed は公開 JSON API だが実測30件は全て発売直後のテスト挨拶（データ価値ゼロ）。

$ python3 fetch_hn2.py  # HN story 実測
```
items/49592840 status= 200
type: story author: nchudleigh title: Show HN: GET Together ... points: 36
```
```
[mdspan] Don't let OpenAI find out about this.
[rickcarlino] This is a honey pot, right? For LLMs that are not allowed to POST due to guard rails.
[jonahss] I made something similar. anystation.net allows GET posting ...
```
→ HN スコア36 / 12コメントで「honeypot / bot警戒 / 同類ツール(anystation.net)既存」が主題（需要・観客ゼロ）。
