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

## 利用するスキル
- `deepseek-coding` — DeepSeek V4でのコード作成
- `claude-code` — Claude Code CLI連携
