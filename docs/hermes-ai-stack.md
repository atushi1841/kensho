# Hermes中核AIエージェントスタック v1.0

> 作成: 2026-09-01 / 最終更新: 2026-09-01
> 目的: Hermes Agentを中核とした個人開発者向け最強AIエージェントスタックの構成記録

## 全体構成

```
┌──────────────────────────────────────────────┐
│  UI/トリガー層                                │
│  Telegram (メイン) · API Server (8642)        │
│  Webhook (8644, n8n-trigger) · n8n制御プレーン │
├──────────────────────────────────────────────┤
│  オーケストレーター                            │
│  Hermes Agent v0.21.0 (Pantheon)              │
│  Kanban Multi-Agent (AI Team稼働中)            │
│  Cron Jobs (25本: 11 active)                  │
│  Persistent Goals (/goal, Ralph loop)         │
├──────────────────────────────────────────────┤
│  MCPツール群 (8個稼働)                         │
│  github · playwright · context7 · n8n         │
│  deepwiki · globalping · hugging_face         │
│  filesystem                                   │
├──────────────────────────────────────────────┤
│  メモリ層                                     │
│  memory_tencentdb (4層L0→L3, カスタム)         │
│  追加候補: Supermemory Local / Honcho / mem0   │
├──────────────────────────────────────────────┤
│  モデルプロバイダ (7段フォールバック)             │
│  bai→openrouter→fireworks→deepseek→nemotron   │
│  →tokenharbor→groq→local_qwen                 │
└──────────────────────────────────────────────┘
```

## 各レイヤーの実装内容

### 1. オーケストレーター: Hermes Agent v0.21.0
- 2026-08-31時点で最新版へ更新済み (1142コミット追従、origin/main同期)
- 主要新機能: Bot Mode(エージェント社会), hermes peer(エージェント間DM),
  Cron記憶(continuity), Subagent steering, MCP command center
- バックエンド: git install (/home/atushi/.hermes/hermes-agent)

### 2. Kanban AI Team (Kensho用)
- ボード: kensho-ai-team
- チェーン: critic → worker → QA (依存リンク)
- ディスパッチャー: Gateway内蔵 (60秒間隔, dispatch_in_gateway: true)
- ★ 2026-09-01: 3ジョブすべてに continuity=true を適用
  (critic 4baf143523e0 / worker 5e8ec4984bba / qa 033ff6065ef7)
  → 実行間で前回出力を記憶し、学習継続可能に

### 3. MCPツール群 (8個)
| サーバー | 用途 |
|---|---|
| github | リポジトリ/PR/Issue管理 |
| playwright | ブラウザ操作・E2E |
| context7 | ライブラリ最新ドキュメント |
| n8n | ワークフロー制御プレーン (stdio bridge) |
| deepwiki | GitHubリポジトリ理解 |
| globalping | ネットワーク診断 |
| hugging_face | MLモデル/データセット |
| filesystem | ファイル操作 |

### 4. メモリ層
- 現行: memory_tencentdb (4層構造: L0会話→L1構造化→L2シーン→L3ペルソナ)
- 追加候補: Supermemory Local (自ホスト), Honcho, mem0
- 切替: `hermes memory setup`

### 5. モデルプロバイダ (7段フォールバック)
- フォールバック順: bai(20s)→openrouter(15s)→fireworks(30s)→deepseek(25s)→
  nemotron→tokenharbor→groq→local_qwen(40s)
- 各リクエストタイムアウトで次へ自動切替
- OpenRouter free 1000/day

## Kensho cron ジョブ一覧 (active)

| ジョブ | スケジュール | 概要 |
|---|---|---|
| apify-auto-publish | 毎日10:00 | Apifyアクター公開自動化 |
| kensho-daily-bot-safety-audit | 毎日1:00 | BOT安全監査 |
| nightly-critic | 20 */2 * * * | 改善提案 (continuity) |
| nightly-worker | 45 */2 * * * | 実装実行 (continuity) |
| nightly-qa | 10 1-23/2 * * * | 検証 (continuity) |
| kensho-daily-applied-recover | 毎日7:50 | applied復元 |
| kensho-hourly-bot-safety-check | 毎時5分 | BOT安全チェック |
| kensho-research-agent | 毎日12:00 | 情報収集 |
| data-sales-accumulate | 毎日0:30 | データ販売蓄積 |
| kensho-research-agent-monetize | 毎日20:00 | 収益化調査 |
| kensho-dataset-weekly-update | 月曜10:00 | データセット更新 |
| kensho-env-weekly-audit | 月曜9:30 | 環境監査 |
| kensho-cron-watchdog | 毎日8:30 | cron失敗監視 |

## 今後の強化候補

1. Persistent Goals (/goal) — 月1-3万収益をRalph loopで自動追跡
2. メモリ層の多検証 — Supermemory Local 追加 (既存スキルあり)
3. MCP Catalog追加 — 必要に応じて (50+候補、無料・要APIキー確認)
4. hermes peer — エージェント間自動連携の高度化
5. Bot Mode — デスクトップアプリでエージェント社会構築

## 2026-09-01 追加（「全部やりたい」対応）

| 追加項目 | 状態 | 詳細 |
|---|---|---|
| **Persistent Goals** | ✅ Kanban --goal card作成 | `t_47a88302` (kensho-sweeps割当て, 20-turn budget) |
| **Supermemory評価** | ✅ 不採用 | no OpenAI/Anthropic key → memory_tencentdb維持 |
| **MCP追加** | ✅ 現状8個最適 | Catalog追加はトークンコスト増のみ、見送り |
| **optimize-storage cron** | ✅ 月次自動化 | 毎月1日3:00, 全profile対象, 742MB解放確認済 |
| **Hermes Dashboard** | ✅ 起動確認 | http://127.0.0.1:9119, Web管理画面 |
| **hermes peer** | ✅ 登録完了 | kensho-sweeps (8642), DM動作確認済 |
| **inobase1-4凍結表示** | ✅ 自動解決 | 15:00更新でdashboard除外完了 |
| **Cron continuity** | ✅ 3ジョブ適用 | critic/worker/qa, 実行間学習 |

## 2026-09-24 追加: エージェント実行テレメトリ (span) の emit 箇所

- **どこで emit しているか**: critic / worker / qa のレポート生成が通る共通ヘルパー `kensho-kanban-sync.sh <role>` の**末尾 1 箇所**が `scripts/agent_span_emit_role.py --agent "$ROLE"`（安全版・`|| true`）を呼び、`data/agent_spans/YYYY-MM-DD.jsonl` に 1 実行 = 1 span を append する（t_4ec92f06 配線。実体: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-kanban-sync.sh` ほか配布コピー 2 本）。

## 参考リンク

- Hermes Docs: https://hermes-agent.nousresearch.com/docs/
- llms.txt: https://hermes-agent.nousresearch.com/docs/llms.txt
- Hermes Atlas: https://hermesatlas.com/ecosystem/
- Persistent Goals: https://hermes-agent.nousresearch.com/docs/user-guide/features/goals
- Memory Providers: https://hermes-agent.nousresearch.com/docs/user-guide/features/memory-providers
