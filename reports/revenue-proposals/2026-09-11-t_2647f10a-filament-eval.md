# 検証記録: Filament (galaxy-io/filament) 非API収益評価（t_2647f10a）

- 対象: https://github.com/galaxy-io/filament / homepage: https://filament.getgalaxy.io / HN: https://news.ycombinator.com/item?id=49611112
- 判断: 却下（実装対象外）— 米スタートアップ Galaxy が自社ETL基盤から切り出した「Go製データレプリケーションエンジン（CDC/checkpointing/batching）」を Apache-2.0 で無料公開したもの。販売可能な公開データセットもホスト型収益サービスも生成されず、Kensho資産（Python scraping + LLM要約）で収集・加工・販売できる対象が構造的に存在しない。スキルの却下濃厚パターン「大企業のOSS開発フレームワーク/OSSライブラリ（Apache/MIT等で無料配布）：収集データ・有料化余地なし → 却下」のそのまま。
- 検出は「自動化キーワード: あり」だが、これは製品内部機能（full/incremental/CDC による自動レプリケーション、checkpoint からの自動再開、integrity events）の記述であり、自動収集・自動配信サービスではない = 誤検出除外枠。

## 3点評価

### 1) プロトタイプ — 不可
- 対象は「ユーザーが自前で接続する DB/S3/Iceberg 間のデータを移すエンジン」であり、著者側にも第三者にも存在する公開データはゼロ。模倣して作れる商品は「無料OSSライブラリの再配布」になる（Apache-2.0）。
- 競合飽和が極端: HNコメント自体が vector.dev との優位性を質問しており、実領域には Airbyte / Debezium / Singer / vector / Materialize 等がひしめく。個人が後発で勝てる隙（ニッチ属性データ）がない。
- Kenshoの収益モデル（懸賞/Scrapling/Apify等の「データを採って売る・処理を自動化して課金する」）に対し、この領域はセルフホストinfraでマネタイズ面が企業SaaS（Galaxy本体）に閉じている。

### 2) ローンチ手順 — 不可
- Kenshoの配置経路（データAPI / 自動化スクリプト / 自前FastAPI / Apify/RapidAPI / ニッチSaaS）のいずれにも乗る商品性がない。インストール経路が curl + Homebrew のバイナリ配布＝既に無料で供給済みであり、有償版を差し出す余地がない。
- 収益モデルの記載はHN本文・READMEともゼロ（オープンソース化は Galaxy の集客ファネル）。販売経路が設計できない以上、プロトタイプ24h着手の対象外。

### 3) 集客 — 不可
- HN実測: points 29 / top-level children 2（内訳は「名前が Filament PHP と衝突」「vector.dev より何が良いの?」という本題外の指摘のみ）＝観客規模が小さく、スクレイピング商材への転用フックなし。スキル基準（score<20で却下材料）の境目だが、上記2点と合わせて単独通過は不可。
- GitHub: star 103 / fork 5 / Apache-2.0・created 2026-06-30（約2か月で103starは速いが高々これだけ）。集客アセット（属性データ / CtoA / 既存トラフィック / 移管可能な観客）はKensho側に一切ない。

## 結論
却下。worker実装タスク（プロトタイプ/ローンチ/集客）は切り出さない。

## verification_evidence

```
$ curl -sL "https://hn.algolia.com/api/v1/items/49611112" -o /tmp/filament_hn.json && jq '{title, points, author, created_at, children: (.children|length)}' /tmp/filament_hn.json
{"title":"Show HN: Filament – Fast data movement engine in Go","points":29,"author":"ikswolzok","created_at":"2026-09-08T14:48:17.000Z","children":2}
$ jq -r '.children[] | select(.text) | .author' /tmp/filament_hn.json | sort | uniq -c
      1 djfobbz
      1 rootshelled
（.children[].text 実測: rootshelled「You are aware that something else with that name exists? filamentphp.com」/ ikswolzok(著者)「Naming is officially harder than cache invalidation :)」/ prideout「There's also github.com/google/filament」/ djfobbz「Does Filament have any specific advantages over vector.dev?」＝機能・収益の手応えある議論なし）
$ curl -sL "https://api.github.com/repos/galaxy-io/filament" -o /tmp/filament_repo.json && jq '{full_name, description, stargazers_count, forks_count, open_issues_count, language, homepage, created_at, pushed_at, license: .license.spdx_id, archived, topics}' /tmp/filament_repo.json
{"full_name":"galaxy-io/filament","description":"Pluggable data replication with checkpointing, batching, and integrity events","stargazers_count":103,"forks_count":5,"open_issues_count":13,"language":"Go","homepage":"https://filament.getgalaxy.io","created_at":"2026-06-30T18:01:23Z","pushed_at":"2026-09-11T04:41:27Z","license":"Apache-2.0","archived":false,"topics":["change-data-capture","data","data-collection","data-integration","data-pipeline","data-replication","elt","etl","golang"]}
$ curl -sL https://raw.githubusercontent.com/galaxy-io/filament/main/README.md | head -40
（実測: "Filament is pluggable data replication with checkpointing, batching, and integrity events... Run Filament as a service with its API and web UI, deploy it to your own infrastructure, or embed the engine in a Go application." Install= `curl -fsSL https://getgalaxy.io/filament/install | sh` / `brew install galaxy-io/tap/filament` / prebuilt binaries on releases page ＝セルフホスト無償配布のみで販売余地なし）
$ curl -sL -o /dev/null -w "homepage -> %{http_code} (%{url_effective})\n" https://filament.getgalaxy.io/
homepage -> 200 (https://filament.getgalaxy.io/pages/guides/get-started/introduction)
$ curl -sL -o /dev/null -w "getgalaxy.io -> %{http_code} (%{url_effective})\n" https://getgalaxy.io/
getgalaxy.io -> 200 (https://www.getgalaxy.io/)
（ベンチマーク https://github.com/galaxy-io/benchmarks も公開=他OSSと比較して無償公開するインフラ部品であり、収集データ・属性データは生成されない）
```

冒頭から証跡セクション末尾まで言及 task_id は t_2647f10a（本タスク）のみ。
