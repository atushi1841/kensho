# Kensho — 懸賞自動化プロジェクト

## プロジェクト概要
国内のX（Twitter）懸賞応募を自動化し、月1〜3万円の副収入を目指す。
いいね・RT・フォローで安全に懸賞当選確率を上げる。
収集源: knshow.com + ken-kaku.com + **kenshou.club** + **cp.meikan.org**（v4.0追加）— 1回の収集で100〜280件取得可能に。

## 絶対ルール（BOT対策）

### 基本方針
1. **人間らしく振る舞う** — 一定間隔のアクションは絶対にしない
2. **ランダム遅延を必ず入れる** — アクション間に最低でも3〜10秒のゆらぎ
3. **一度に大量アクションしない** — 1セッション最大15〜20件まで
4. **リプライ＋他アクションの同時実行禁止** — リプライは単独でのみ実行する（いいね＋リプライ同時NG）

### X/Twitter運用ルール
- フォロー/RT/いいねは同一ツイートでも実行可（当選条件「フォロー＆RT＆いいね」を満たすために必要な正常行動）
- リプライのみは単独で実行（1回のセッションではリプライ1種類だけ）
- リプライはテンプレートではなく、その投稿に合わせた自然な内容に
- 1時間に20件以上のアクションをしない
- アカウントごとに異なる行動パターンを持つ
- Chromeの通常ブラウジングを模倣（マウス移動、スクロール）
- スパム報告されそうな挙動（同一文言の連投、短時間の大量フォロー）は絶対に避ける

### 運用スケジュール
- 収集: 毎正時（9〜21時、1日13回）
- 応募: 各アカウント5バッチに分散（atushi16は75件/day、他は50件/day）
- 各セッション15分以内
- 同じ時間帯に毎日実行しない（曜日で変える）

## コード構成
- `kensho_collect.py` — データ収集
- `kensho_apply_single.py` — 単一適用
- `kensho_cron_worker.py` — cron定期ワーカー
- `orchestrator.py` — 全体オーケストレーター
- `scraping/` — スクレイピングモジュール
- `application/` — 応募処理
- `core/` — コア機能（config, logger, notifier, encoding, cleanup, self_heal）
- `keepalive/` — ネットワーク監視（checker, wifi_manager）
- `utils/` — ユーティリティ（backup, network, process）
- `scripts/` — 補助スクリプト（health check, cron worker）
- `tests/` — pytestテスト（51テスト、mypy strict 0 error）
- `bin/claude-pro` — DeepSeek V4 Pro コード作成
- `bin/claude-flash` — DeepSeek V4 Flash コード作成

## 設定ファイル
- `config.yaml` — プロジェクト全体設定

## アカウント管理
- アカウント追加時は `config.yaml` の `accounts:` セクションに追記
- Xセッションファイルは `data/x_session_<key>.json`
- ネットワークI/FはUSB HUB経由でIP分離

## 外部AIエージェント（freebuff / Codex / Claude Code 等）に渡すときの禁止事項

このリポジトリを外部のコーディングエージェントに渡す場合、以下を厳守すること。

- **読むな・触るな（認証情報）**: `.env`, `data/x_session_*.json`, `.secret-local/`,
  `data/backups/`, `data/session_backup/`
  → Xアカウントのセッション・APIキーが入っている。外部モデルに学習利用される危険がある
- **変更するな**: `config.yaml` の `accounts:` セクション（アカウント管理は人間が手動で行う）
- **実行するな**: 実ブラウザでの X 操作（応募・ログイン・スクレイピングの実行）
- **作業対象**: `kensho/`, `tests/`, `scripts/` 配下のコード、および `tests/` の実行のみ

## 利用するスキル
- `deepseek-coding` — DeepSeek V4でのコード作成
- `claude-code` — Claude Code CLI連携

## セキュリティ規則（2026-10-04 追加・厳守）

**背景**: AIチームが個人用X自動化コードを public リポジトリで公開してしまい、Apify APIトークンが
`data/revenue-daily.json` 経由で漏洩（GitHub Secret Scanning 検知）。以下は例外なく守ること。

1. **公開リポジトリへの push 禁止**。push 先は private の `atushi1841/kensho` のみ。
   `git remote -v` で private であることを確認してから push する。
2. **新規リポジトリは必ず private で作成**する。公開が必須な商品リポジトリ（MCPサーバー等）は
   オーナーの明示的な承認を得てから public にする。
3. **秘密情報をURLに載せない**。`?token=...` のクエリ渡しは禁止。必ず
   `Authorization: Bearer <token>` ヘッダで送る（`scripts/_apify_auth.py` を使う）。
   URL内トークンは requests/urllib の例外文に混入し、それがJSONやログに保存されて漏洩する。
4. 秘密情報は `.env`（git追跡外）のみに置く。コード・データ・state・ログへ書き出さない。
   やむを得ず例外文を保存する場合は `redact_secrets()` を通す。
5. push 前に `.git/hooks/pre-push` が秘密パターンを検査する。検出されたら push は中止される
   （apify_api_ / ghp_ / github_pat_ / sk- / AKIA / Slack / 秘密鍵）。
6. 収益・状態系のJSONは特に注意（外部APIの例外文が保存されやすい）。
