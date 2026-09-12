# 検証記録: hnslop（Show HN: Extension to filter LLM written articles）非API収益評価（t_6e2d4279）

- 対象: https://hnslop.nilsherzig.com/ / GitHub: https://github.com/nilsherzig/hnslop / 上流データ: https://www.salahadawi.com/hacker-news-ai-detector / HN: https://news.ycombinator.com/item?id=49661856
- 判断: 却下（実装対象外）— 「Salah Adawi の HN AI Detector（=Pangram v3.3 有償APIを第三者が手払いで回した結果）」をキャッシュして無料で公開しているだけの JSON API + Firefox拡張/ユーザースクリプト。実測で本APIは検出を一切その場で行わない（キャッシュヒット専用、miss は upstream_status 404 を返す）ことが確認できた。生成元から既に無料配布済みのデータを転売する独占性が構造的にゼロであり、スキルの却下濃厚パターン「公開ソースの集約で誰でも再現可能＝コモディティ」＋「OSS/無料ツール（license=null、有料版なし）」に該当。
- 検出は「自動化キーワード: あり」だが、これは製品内部機能（フロントページのスコアを拡張が自動で表示・非表示）の記述であり、自動収集・自動配信サービスではない = 誤検出除外枠（t_bcf06c00 dbmask、t_f000bf35 Egma と同一パターン）。

## 3点評価

### 1) プロトタイプ — 不可
- 商品の中身は「HN全記事の Pangram AI スコア」だが、その生データは第三者 Salah が Pangram 有償APIを課金して生成済みで、hnslop 側はキャッシュ再配布のみ（self-description: "turns Salah Adawi's Hacker News AI Detector into a cached JSON API"）。Kensho が模倣して作れるのは「他人が無料公開済みのスコア列の再ミラー」で、支払う Pangram コスト（サイト自身が "sell multiple internal organs to pay for his pangram usage" と明記）だけを抱える無価値な複製になる。
- 一歩一般化した「AI検出を他市場（レビュー・記事・求人）へ転用する検出API」も、Pangram / GPTZero が直接セルフサーブの有償APIを販売済みで、転売経路に余地なし。Kensho の Python scraping + LLM 資産を活かす独自収集対象（独占性・再現困難性のあるデータ）が存在しない。
- 供給の安定性も欠陥: 上流（Salah の個人プロジェクト・単発ラン）が止まればデータは更新停止する従属構造。

### 2) ローンチ手順 — 不可
- Kensho の配置経路（データAPI / 自前FastAPI / Apify/RapidAPI / ニッチSaaS）に載せても、販売対象が「無料公開済みの同一データ」なので価格が成立しない。hnslop 自身に pricing・アカウント・APIキー・利用制限の類は一切なし（"Feel free to use the hosted instance"）。
- ローンチ経路とは別軸の事業リスクとして、HN記事テキストに有料検出モデルを当てて再配布する行為自体が上流 Pangram / Salah の規約上のグレーゾーンであり、収益商品としての監査耐性がない。

### 3) 集客 — 不可
- HN実測: score 16 / descendants 2（質問1+作者返信1のみ、批評も需要シグナルも無し）。スキル基準 score<20 の却下材料に該当し、観客規模が微小。
- GitHub: stars 0 / forks 0 / created 2026-09-06（約1週間）/ license=null / language=Go。作者の集客アセットも Kensho 側の移管可能観客（既存トラフィック・X属性データ・CtoA）もこのテーマには存在しない。

## 結論
却下。worker 実装タスク（プロトタイプ/ローンチ/集客）は切り出さない。

## verification_evidence

```
$ curl -sL -A 'Mozilla/5.0 ... Chrome/128.0' https://hnslop.nilsherzig.com/ -o site_root.html
root: 200 text/html; charset=utf-8 8862（robots.txt / sitemap.xml は "404 page not found"＝SEO/クロール設計なしの単発ページ）
meta description="hnslop provides Pangram scores for Hacker News posts through a JSON API and Firefox extension."
本文="This server turns Salah Adawi's Hacker News AI Detector into a cached JSON API... Feel free to use the hosted instance... Salah is using Pangram v3.3" + "(i assume that he had to sell multiple internal organs to pay for his pangram usage)"（＝データ生成コストは第三者Salah負担、本サイトはキャッシュ再配布のみ、の自己申告）
$ curl -s https://hacker-news.firebaseio.com/v0/item/49661856.json
{"by":"nilsherzig","descendants":2,"id":49661856,"kids":[49668456],"score":16,"time":1789146889,"title":"Show HN: Extension to filter LLM written articles"}
$ curl -s https://hacker-news.firebaseio.com/v0/item/49668456.json ; curl -s https://hacker-news.firebaseio.com/v0/item/49669690.json
sriyapaka: "How does the scoring work, since AI-assisted useful content is always fine?" / nilsherzig: Pangram research へのリンク返信のみ（＝計2コメント、需要・課金シグナル無し）
$ curl -s 'https://hnslop.nilsherzig.com/v1/posts/49582582'
{"id":49582582,"detector":{"ai_score":33,"url":"https://www.salahadawi.com/hacker-news-ai-detector/49582582"},"cache_status":"hit"}
$ curl -s 'https://hnslop.nilsherzig.com/v1/posts/49661856'
{"id":49661856,"detector":null,"cache_status":"bypass","upstream_status":404}（＝未キャッシュ分のその場検出は行わない=Salah済みの結果専有物。検出自体は第三者の有償Pangram利用が生産している）
$ curl -s 'https://hnslop.nilsherzig.com/v1/posts' → 400 / '/v1/frontpage' → 404 / '/openapi.json' → 404（API表面は /v1/posts 単一、成約面・認証・レート課金の設計なし）
$ curl -s https://api.github.com/repos/nilsherzig/hnslop
language=Go stargazers_count=0 forks_count=0 license=null created_at=2026-09-06T11:43:58Z pushed_at=2026-09-11T20:28:03Z
$ curl -s https://www.salahadawi.com/hacker-news-ai-detector
200 72345bytes、"Pangram's AI detector" / "Pangram v3.3 · published"（上流も個人趣味プロジェクトで商用提供面なし）
```

冒頭から証跡セクション末尾まで言及 task_id は t_6e2d4279（本タスク）のみ。
