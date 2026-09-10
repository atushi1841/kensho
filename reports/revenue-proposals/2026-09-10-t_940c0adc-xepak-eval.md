# 検証記録: Xepak (rustrum/xepak) 非API収益評価（t_940c0adc）

- 対象: https://github.com/rustrum/xepak / HN: https://news.ycombinator.com/item?id=49630394
- 判断: 却下（実装対象外）— 「PostgRESTのRust代替」を作る個人OSS開発者ツール（SQLite DBにTOML DSL+LUAでRESTエンドポイントを生成させるセルフホストサーバー）。MVP前の開発途中プロジェクトで、公開データセットもホスト型サービスも収益化可能な生成物も存在しない。Kensho資産（Python scraping + LLM要約）で収集・加工・販売できる対象が構造的に存在せず、模倣したところで「DBからAPIを生やすOSSライブラリ」を無料で配ることになる（MIT）= スキル所定の「OSS開発フレームワーク/OSSライブラリ：収集データ・有料化余地なし → 却下」パターンのそのまま。
- 検出は「自動化キーワード: あり」だが、これは製品内部機能（DBからのエンドポイント自動生成、LUA/Rhaiによる自動バリデーション・レート制限）の記述であり、自動収集・自動配信サービスではない = 誤検出除外枠。

## 3点評価

### 1) プロトタイプ — 不可
- 対象はGitHubリポジトリのみ（homepage空、gh-pages 404、crates.io未公開）。デモもAPIもデータも無し。収集できる公開データが一切存在しない——このツールが生成するのは「ユーザー自身のSQLite DBの中身」であり、それは作者にも第三者にも存在しない。
- 開発ステータス: README明記の通り「first MVP release in the next month」「bookmark and visit this project later」＝まだ一般提供されていない。README-TODO.md で POST リクエストが「does not work now」、アーキテクチャ決定（RequestInput最適化、Rhai vs LUA）も未着地。
- 再現の可否は無意味: 仮にKenshoがFastAPI+SQLiteで同等の「DSL→REST生成器」を作れたとして、販売対象（独占データ）が乗らない。ツール自体はMIT+CLAで無料配布されており、有料商品は成立しない。

### 2) ローンチ手順 — 不可
- Kenshoの配置経路（データAPI / 自動化スクリプト / 自前FastAPI / Apify/RapidAPI / ニッチSaaS）のいずれにも乗る商品性がない。データ追跡・通知系のニッチSaaSと違い、これはインフラ部品（PostgREST/Diesel/SurrealDB等の飽和した自己領域のOSS開発ツール）で、競合はPostgREST本体・supersql等の既存Rust系を含む多数。
- 作者自身の動機は技術的不服（Haskell/PLSQLを本番で使いたくない）であり、収益モデルの記載はゼロ。販売経路が設計できない。

### 3) 集客 — 不可
- HN本体が score 4 / comments 0（2026-09-09投稿、実測でchildren=[]）＝観客規模がほぼゼロ。スキル基準（score<20で却下材料）を大きく下回る。
- GitHub実績も star 1 / fork 0 / open issues 0。集客アセット（属性データ / CtoA / 既存トラフィック / 既存観客）はKensho側に一切なく、移管可能な観客も無い。

## 結論
却下。worker実装タスク（プロトタイプ/ローンチ/集客）は切り出さない。

## verification_evidence

```
$ curl -s "https://hn.algolia.com/api/v1/items/49630394" | jq -r '.title, .points, .author, .created_at, (.children|length)'
Show HN: I'm not a PostgREST fan this is why I'm building an alternative
4
rumatoest
2026-09-09T17:47:41.000Z
0
$ curl -s "https://api.github.com/repos/rustrum/xepak" | jq '{full_name,description,stargazers_count,forks_count,open_issues_count,language,homepage,created_at,pushed_at,license:.license.spdx_id}'
{
  "full_name": "rustrum/xepak",
  "description": "DSL based REST service for your Sqlite database (more DB will be supported later)",
  "stargazers_count": 1,
  "forks_count": 0,
  "open_issues_count": 0,
  "language": "Rust",
  "homepage": "",
  "created_at": "2026-01-10T16:33:03Z",
  "pushed_at": "2026-09-09T17:54:38Z",
  "license": "MIT"
}
$ curl -sL https://raw.githubusercontent.com/rustrum/xepak/main/README.md | head -20
（TL;DR: "Imagine PostgREST but instead of Haskell with PL/SQL it is based on Rust with LUA and focused on Sqlite" / status: "I'm aiming for a first MVP release in the next month" "I encourage you to bookmark and visit this project later"）
$ curl -sL https://raw.githubusercontent.com/rustrum/xepak/main/README-TODO.md | head -4
# POST request
look for request_type="POST" it is exists in DSL but does not work now
（POST未実装・アーキテクチャ未確定が実測）
$ curl -sL -o /dev/null -w "crates.io xepak -> %{http_code}\n" https://crates.io/api/v1/crates/xepak
crates.io xepak -> 403
$ curl -sL -o /dev/null -w "github pages -> %{http_code}\n" https://rustrum.github.io/xepak/
github pages -> 404
$ curl -sL https://api.github.com/repos/rustrum/xepak/git/trees/main?recursive=1 | jq -r '.tree[].path' | head -20
（.cargo / behind/ / examples/xepak/specs/*.toml / README-AI.md / LICENSE-TERMS のみで、デモサービス・データ配布・リリースバイナリ無し）
```

冒頭から証跡セクション末尾まで言及 task_id は t_940c0adc（本タスク）のみ。
