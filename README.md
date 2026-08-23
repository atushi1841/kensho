# Kensho — X懸賞自動応募システム

X（Twitter）の懸賞応募（いいね・RT・フォロー）を完全自動化。
**5アカウント** で稼働、月1〜3万円の副収入を目指します。

## クイックスタート

```bash
cd /mnt/d/Project2/kensho

# セットアップ
python -m venv ~/kensho-venv
source ~/kensho-venv/bin/activate
pip install -e ".[dev]"
pre-commit install

# テスト実行
make test

# 収集のみ
python kensho/kensho_collect.py --max-items 10 --pages 1

# 応募（1垢、最大N件）
python kensho/kensho_apply_single.py atushi16 5

# 常駐デーモン
python kensho/daemon.py
```

## ディレクトリ構成

```
/mnt/d/Project2/kensho/
├── kensho/                       # 全Pythonコード
│   ├── orchestrator.py           # オーケストレーター（15分おき）
│   ├── kensho_collect.py         # CLIラッパー
│   ├── kensho_apply_single.py    # 単一アカウント応募
│   ├── daemon.py                 # 常駐デーモン
│   ├── application/
│   │   ├── applier.py            # 応募ロジック（Like/RT/Follow）
│   │   ├── browser.py            # invisible_playwright Firefox制御
│   │   ├── rate_limiter.py       # レート制限・動作時間管理
│   │   ├── reply_generator.py    # リプライ生成（未使用）
│   │   ├── session_manager.py    # Xセッション管理
│   │   └── state.py              # 応募状態管理
│   ├── core/
│   │   ├── config.py             # 設定読み込み（YAML + Pydantic v2モデル）
│   │   ├── logger.py             # ログ出力（loguru）
│   │   ├── cleanup.py            # ゾンビプロセス掃除（psutil）
│   │   ├── crash_guard.py        # クラッシュガード
│   │   ├── encoding.py           # UTF-8ガード
│   │   ├── lock.py               # PIDロック
│   │   └── notifier.py           # 通知
│   ├── scraping/                 # 収集エンジン
│   │   ├── collector.py
│   │   └── sources/              # 収集元サイト別パーサー
│   ├── utils/
│   │   ├── backup.py             # 自動バックアップ/復旧
│   │   ├── keyring.py            # Xセッション管理
│   │   ├── network.py            # ネットワークユーティリティ
│   │   ├── process.py            # サブプロセス実行
│   │   └── safety.py             # IP分離チェック
│   ├── keepalive/                # ネットワーク監視
│   └── tools/                    # 診断・保守ツール
├── scripts/                      # シェルスクリプト（cron, health check）
├── tests/                        # pytest（104 passed, 4 skipped）
├── data/                         # JSONデータ類
├── logs/                         # ログ（日付別）
├── config.yaml                   # 全体設定
├── pyproject.toml                # プロジェクト管理
├── .pre-commit-config.yaml       # pre-commit設定
├── Makefile                      # タスクランナー
├── .github/workflows/ci.yml      # GitHub Actions CI
└── README.md
```

## 開発用コマンド

```bash
make test       # テスト実行（104 passed）
make lint      # Ruff Lint
make format    # Ruff Format
make setup     # 依存関係 + pre-commit インストール
make coverage  # カバレッジレポート
```

## 情報検索

```bash
# Xのツイート内容を読む（認証不要）
web_search xfetch "https://x.com/user/status/123456789"

# Xの投稿を検索
web_search xsearch "invisible_playwright reCAPTCHA"

# 5chのスレッドを検索
web_search fch "懸賞 自動応募"
```

## 運用ルール

- **稼働時間**: 09:00〜22:00
- **1セッション最大**: 5件（config.yamlで調整可）
- **日次上限**: フォロー50 / RT 15 / いいね80 / 垢
- **アクション間隔**: 15〜50秒（人間らしいランダム）
- **応募方式**: フォロー/RT/いいねのみ（リプライ廃止）
- **BOT対策**: invisible_playwright + C++レベル指紋偽装 + アカウント別UA

## 5アカウント構成

| アカウント | 役割 | バッチ数 | 日次最大 |
|:----------|:----|:--------:|:--------:|
| @atushi16 | 収集＋応募 | 3回 | 45件 |
| @kudou_aoshi | 応募のみ | 5回 | 50件 |
| @chugakujuken | 応募のみ | 5回 | 50件 |
| @zin20120731 | 応募のみ | 5回 | 50件 |
| @TankanNotes | 応募のみ | 5回 | 50件 |

## 技術スタック

| 要素 | 採用技術 |
|------|---------|
| ブラウザ自動化 | **invisible_playwright** (Firefox 150.0.1, C++レベル指紋偽装) |
| BOT検出回避 | reCAPTCHA v3 score 0.9, CreepJS零警告 |
| 設定管理 | **Pydantic v2** 型安全モデル (KenshoConfig) |
| ログ | **loguru** (自動ローテーション) |
| Lint/Format | **Ruff** (pre-commit統合) |
| 型チェック | **mypy** (strict設定) |
| CI/CD | GitHub Actions (Lint + 72テスト) |
| プロキシ | SOCKS5（アカウント別IP対応） |
| 実行環境 | WSL2 (Ubuntu) on Windows 11 |

## 関連リソース

- **Hermes Agent profile**: `kensho-sweeps`
- **設定ファイル**: `~/.hermes/profiles/kensho-sweeps/config.yaml`
- **cronジョブ**: 15分おき（active_hours内のみ）
- **Obsidian vault**: `../kensho-wiki/`（プロジェクト外）
