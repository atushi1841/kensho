# 非API収益 評価レポート

- タスク: t_d78dde9e
- 対象: Show HN: Engrim – A universal, local-first SQLite memory engine for AI CLIs
- 元記事HN: https://news.ycombinator.com/item?id=49594008
- 対象URL: https://github.com/timgordontg/engrim
- 宣伝元: kensho-non-api-revenue-hunter（score 10 / コメント 1 有効で検出）
- 評価日: 2026-09-07
- 評価者: kensho-revenue-worker
- 判定: **非収益タスク（却下 / 実装対象外）**

## 実態確認（実測データ）
- GitHub リポジトリ `timgordontg/engrim` 実在。Python 製、created 2026-06-19。stars 14 / forks 2 / watchers 14（規模極小）。
- PyPI 公開済み `engrim`（Development Status 4 - Beta、License MIT、Python 3.10+）。`pip install engrim` で無料インストール。
- 機能: ローカル優先の SQLite メモリエンジン。Claude Code / Google Antigravity / Cursor / Windsurf のエージェント間でプロジェクトの決定・制約・状態を永続化。FTS5 + model2vec（ローカル静的 embedding）のハイブリッド検索、MCP stdio サーバ、hook 設定を自動配線する `engrim setup`。
- 収益モデル: 記載なし。MIT OSS 無料公開。sponsorship・有償 docs・SaaS・クラウド版の記述なし（"Zero cloud lock-in" / "100% Local & Offline" と明言）。
- 自動化ワード（setup の auto-detection / "autonomous coding" / "Continue-As-Clear"）は全部ローカル開発ツール内部の hook・配線・ワークフロー機能であり、収集データや配信商品ではない → 誤検出。

## 3点評価
### 1) プロトタイプ — 不成立
- Kensho 資産（Python scraping + LLM 要約）で作り直せる対象データが存在しない。本件は「データ商品」ではなく「開発者向け OSS ライブラリ」。
- スクレイピング対象・公開RSS・公開API・DL可能DS が全て不在。ローカル SQLite に閉じた処理で、集約すべき生データも外部ソースも無い。
- 独占性・再現困難性なし。同等のローカルメモリ/コンテキスト永続化（CLAUDE.md、Codex、mem0 等）で代替可能なコモディティ領域。

### 2) ローンチ手順 — 不成立
- Kensho の配置経路（データAPI / 自動化 / 自前FastAPI / Apify/RapidAPI）のいずれにも乗らない。
- 収益化には OSS 継続開発 → GitHub Sponsors / コンサル等の長期事業が必須で受動収益に非適合。marketplace 型の販売・置き場が無い。

### 3) 集客 — 微小（却下材料）
- HN score 10（既却下の Model ORM は score 4）と依然低値、有効コメント 1 件。GitHub 14 stars。観客規模は微小。
- 開発者ツール向けの既存トラフィック・CtoA・Kensho 側の観客アセットも不在。

## 結論
実体は無料公開された MIT OSS 開発者ツール（ローカル SQLite メモリライブラリ）。データ商品・スクレイピング・販売ツール・集客素材のいずれも構成できず、Apify/RapidAPI 以外の手法で Kensho の月1-3万円収益商品にできない。典型的な却下対象。「自動化ワード」は開発ツール内部機能記述の誤検出。既却下の Model ORM と同一カテゴリ・同一結論。

## verification_evidence
下記コマンドで対象の実体・規模・収益モデルを実測した（タスク t_d78dde9e の証跡）。

```
$ curl -sL "https://hacker-news.firebaseio.com/v0/item/49594008.json"
  → {"by":"timgordontg","descendants":1,"score":10,"title":"Show HN: Engrim - ..."}
    （score 10 / コメント 4 中 3 は flagged/dead、有効1件のみ「Codex?」）

$ curl -sL https://hacker-news.firebaseio.com/v0/item/49594026.json
  → {"by":"timgordontg","dead":true,"text":"[flagged]"}
    （投稿者自身のコメントが flagged → HN での正当な議論はほぼ無い）

$ curl -sL "https://api.github.com/repos/timgordontg/engrim"
  → stargazers_count=14, forks_count=2, language=Python, license.spdx_id=MIT,
    description="...Local-first, project-scoped SQLite memory engine...Zero cloud lock-in"

$ curl -sL "https://pypi.org/pypi/engrim/json"
  → version 1.3.0, classifiers=["Development Status :: 4 - Beta",
    "License :: OSI Approved :: MIT License"], requires_python 相当、無料 pip install

$ curl -sL "https://raw.githubusercontent.com/timgordontg/engrim/main/README.md"
  → README より: install "pip install engrim"、第9節 Security & Privacy
    "100% Local & Offline ... no cloud, no telemetry"、第10節 License "MIT © 2026"
    → 有料化モデル・スクレイピング対象・データ商品の記述は一切無し
```

結論エビデンス: 無料 OSS（MIT / PyPI / local-first）、観客極小（stars 14 / HN score 10, 有効コメント1）、収益化経路・スクレイピング対象・データ商品が全て無いことを 5 コマンドの実測で確認。
