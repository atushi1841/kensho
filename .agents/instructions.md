# Kensho — エージェント用プロジェクトルール（.agents/instructions.md）

このファイルは `freebuff --trust-agents` 実行時に自動読込される、外部AIエージェント向けの正本ルール。
`AGENTS.md` と同じ方針。矛盾が生じた場合は **安全側（禁止を優先）** を選ぶこと。

## プロジェクト概要
国内のX（Twitter）懸賞応募を自動化し、月1〜3万円の副収入を目指す。
いいね・RT・フォローで安全に懸賞当選確率を上げる。
収集源: knshow.com + ken-kaku.com + kenshou.club + cp.meikan.org。

## 絶対ルール（BOT対策）
1. **人間らしく振る舞う** — 一定間隔のアクションは絶対にしない
2. **ランダム遅延を必ず入れる** — アクション間に最低でも3〜10秒のゆらぎ
3. **一度に大量アクションしない** — 1セッション最大15〜20件まで
4. **リプライ＋他アクションの同時実行禁止** — リプライは単独でのみ実行する
5. 1時間に20件以上のアクションをしない
6. スパム報告されそうな挙動（同一文言の連投、短時間の大量フォロー）は絶対に避ける

## エージェント作業時の禁止事項（最重要）

### 読むな・触るな（認証情報）
- `.env`, `data/x_session_*.json`, `.secret-local/`, `data/backups/`, `data/session_backup/`
  → Xアカウントのセッション・APIキーが入っている

### 変更するな
- `config.yaml` の `accounts:` セクション（アカウント管理は人間が手動で行う）

### 実行するな
- 実ブラウザでの X 操作（応募・ログイン・スクレイピングの実行）
- ネットワーク越しのX操作全般

### 作業対象
- `kensho/`, `tests/`, `scripts/` 配下のコード、および `tests/` の実行のみ

## 開発コマンド
```bash
# テスト（カバレッジなしで高速）
./.venv/bin/python -m pytest tests/ -q --no-cov

# 全チェック（lint + mypy + test）
make check

# 個別
make lint    # ruff check kensho/ tests/
make mypy    # python -m mypy kensho/ --ignore-missing-imports
make format  # ruff format kensho/ tests/
```

## コード規約
- Python 3.12, line-length 120（ruff）
- 型ヒント必須（新規コードは mypy strict 相当を意識）
- テストは `tests/` 配下、既存スタイルに合わせる（クラス＋日本語docstring）
- テストは `tmp_path` / `monkeypatch` で外部依存を分離、ネットワーク・実ブラウザ禁止

## コード構成
- `kensho_collect.py` / `kensho_apply_single.py` / `kensho_cron_worker.py` — エントリポイント
- `orchestrator.py` — 全体オーケストレーター
- `scraping/` — スクレイピング、`application/` — 応募処理
- `core/` — config, logger, notifier, encoding, cleanup, self_heal
- `keepalive/` — ネットワーク監視、`utils/` — backup, network, process
