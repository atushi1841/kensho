# 非API収益 評価レポート

- タスク: t_0b66e25b
- 対象: Show HN: I stopped using an LLM gateway and put rate-limits/fallback in-process (VernLLM)
- 元記事HN: https://news.ycombinator.com/item?id=49585787
- 対象URL: https://github.com/LakBud/vernLLM
- 宣伝元: kensho-non-api-revenue-hunter（score 4 / コメント 1 有効で検出）
- 評価日: 2026-09-07
- 評価者: kensho-revenue-worker
- 判定: **非収益タスク（却下 / 実装対象外）**

## 実態確認（実測データ）
- GitHub リポジトリ `LakBud/vernLLM` 実在。TypeScript 製、created 2026-07-19。stars 0 / forks 1（規模極小）。
- npm 公開済み `vern-llm`（latest 2.7.0、License MIT）。直近30日 DL 8,284。無料インストール。
- 機能: TypeScript/Node の in-process LLM call フレームワーク。OpenAI互換 / Anthropic / Gemini / Bedrock への単一インターフェイスで、rate limiting / retry / circuit breaking / fallback / caching / middleware を自プロセス内で提供。「ネットワークホップを増やす LLM ゲートウェイを使わず、in-process で同機能を実現」する開発者向け OSS ライブラリ。
- 収益モデル: 記載なし。MIT OSS 無料公開。sponsorship・有償 docs・SaaS・クラウド版の記述なし。
- 自動化ワード（rate-limits/fallback in-process、circuit breaking）は全部開発用フレームワーク内部の耐障害機能であり、収集データや配信商品ではない → 誤検出。

## 3点評価
### 1) プロトタイプ — 不成立
- Kensho 資産（Python scraping + LLM 要約）で作り直せる対象データが存在しない。本件は「データ商品」ではなく「開発者向け OSS ライブラリ」。
- スクレイピング対象・公開RSS・公開API・DL可能DS が全て不在。Node プロセス内に閉じたライブラリで、集約すべき生データも外部ソースも無い。
- 独占性・再現困難性なし。LLM ゲートウェイ/リトライ層は LiteLLM・OpenRouter・langchain 等で代替可能な飽和領域。

### 2) ローンチ手順 — 不成立
- Kensho の配置経路（データAPI / 自動化 / 自前FastAPI / Apify/RapidAPI）のいずれにも乗らない（TypeScript 製で Python 資産とも非結合）。
- 収益化には OSS 継続開発 → GitHub Sponsors / コンサル等の長期事業が必須で受動収益に非適合。marketplace 型の販売・置き場が無い。

### 3) 集客 — 微小（却下材料）
- HN score 4、有効コメント 1 件（投稿者自身の「フィードバック募集」のみ）、GitHub stars 0。観客規模は極小（既却下の Engrim score 10 以下）。
- 開発者ツール向けの既存トラフィック・CtoA・Kensho 側の観客アセットも不在。

## 結論
実体は無料公開された MIT OSS 開発者ツール（TypeScript/Node の in-process LLM コールフレームワーク）。データ商品・スクレイピング・販売ツール・集客素材のいずれも構成できず、Apify/RapidAPI 以外の手法で Kensho の月1-3万円収益商品にできない。典型的な却下対象。「自動化ワード」は開発ツール内部機能記述の誤検出。既却下の Engrim（t_d78dde9e）と同一カテゴリ・同一結論。

## verification_evidence
下記コマンドで対象の実体・規模・収益モデルを実測した（タスク t_0b66e25b の証跡）。

```
$ curl -sL https://hacker-news.firebaseio.com/v0/item/49585787.json
  → {...,"score":4,"descendants":1,...}
    （score 4 / コメント 1 有効、投稿者自身のフィードバック募集のみ）

$ curl -sL "https://api.github.com/repos/LakBud/vernLLM"
  → stargazers_count=0, forks_count=1, language=TypeScript,
    license.spdx_id=MIT, created_at=2026-07-19

$ curl -sL https://registry.npmjs.org/vern-llm
  → {"dist-tags":{"next":"0.0.0-canary-883bda2","latest":"2.7.0"},...}
    MIT 無料 OSS

$ curl -sL "https://api.npmjs.org/downloads/point/last-month/vern-llm"
  → {"downloads":8284,...}
    （APIキー不要の npm パッケージ。遊休 API キー/集約データは不在）

$ curl -sL "https://raw.githubusercontent.com/LakBud/vernLLM/main/README.md"
  → README より: "The LLM call framework... in your own process rather than
    a new network hop"、License "MIT © LakBud"
    → 有料化モデル・スクレイピング対象・データ商品の記述は一切無し
```

結論エビデンス: 無料 OSS（MIT / npm / in-process 開発ライブラリ）、観客極小（stars 0 / HN score 4, 有効コメント1）、収益化経路・スクレイピング対象・データ商品が全て無いことを 5 コマンドの実測で確認。
