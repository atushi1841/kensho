# Kensho — X懸賞自動化プロジェクト

国内のX（Twitter）懸賞応募を完全自動化し、月1〜3万円の副収入を目指します。

## 概要

- **4つのXアカウント**をIP分離して運用
- **knshow.com** から懸賞URLを自動収集
- **Playwright Firefox** でいいね・RT・フォロー・リプライを自動実行
- **月1〜3万円**の副収入目標
- **週1時間**の確認作業のみ

## クイックスタート

```bash
cd D:\Project2\kensho

# 初回セットアップ（Playwright用Firefoxインストール）
pip install -r requirements.txt
playwright install firefox

# 収集のみ
python kensho_collect.py --max-items 10 --pages 1

# 応募（1垢、最大N件）
python kensho_apply_single.py atushi16 5

# 常駐デーモン起動（窓ゼロ、自動ループ）
python daemon.py
```

> **注意:** 初回は `playwright install firefox` を**必ず実行**してください。  
> インストールしないとブラウザ起動に失敗します。

## プロファイル

- Hermes Agent プロファイル: `kensho-sweeps`
- 設定: `~/.hermes/profiles/kensho-sweeps/config.yaml`

## ディレクトリ構成

```
D:\Project2\kensho\
├── config.yaml                  # 全体設定
├── daemon.py                    # 常駐デーモン（3スレッド）
├── orchestrator.py              # オーケストレーター（15分おき）
├── kensho_collect.py            # CLIラッパー（scraping/collectorに委譲）
├── kensho_apply_single.py       # 単一アカウント応募
├── application/
│   ├── applier.py               # 応募ロジック（Like/RT/Follow/Reply）
│   ├── browser.py               # Playwright Firefox制御 + 指紋偽装
│   └── session_manager.py       # Xセッション管理
├── scraping/
│   └── collector.py             # knshow.com収集エンジン
├── core/
│   ├── config.py                # 設定読み込み
│   ├── cleanup.py               # ゾンビ掃除
│   ├── logger.py                # ログ出力
│   └── notifier.py              # Windowsトースト通知
├── keepalive/                   # ネットワーク監視
├── utils/
│   ├── backup.py                # 自動バックアップ/復旧
│   └── network.py               # ネットワークユーティリティ
├── scripts/                     # 補助スクリプト
├── data/
│   ├── collected.json           # 収集懸賞リスト＋応募状態
│   ├── processed.json           # 処理済みID一覧
│   ├── daily_counts.json        # 日次カウンター
│   └── x_session*.json          # Xセッション（認証情報）
├── logs/                        # ログ（日付別）
└── requirements.txt             # 依存パッケージ
```

## 運用ルール

1. **稼働時間**: 09:00〜23:59（深夜は絶対停止）
2. **1セッション最大**: 15件
3. **1時間最大**: 20アクション
4. **日次上限**: フォロー120 / RT 80 / いいね200 / リプライ10
5. **アクション間隔**: 12〜40秒（人間らしいランダム）
6. **同一ツイート連続アクション禁止**

## 4アカウント構成

| アカウント | 役割 | バッチ数 | 日次最大 |
|:----------|:----|:--------:|:--------:|
| @atushi16 | 収集＋応募 | 3回 | 45件 |
| @kudou_aoshi | 応募のみ | 5回 | 50件 |
| @atushi1840 | 応募のみ | 5回 | 50件 |
| @zin20120731 | 応募のみ | 5回 | 50件 |

## 注意事項

- XのBOTと判定されると**警告なしで凍結**されます
- 必ず **IP分離**（ForceBindIP）＋**アカウント別指紋偽装**で運用
- セッション期限: auth_token は無期限、ct0 は約1年有効
- collected.json は自動バックアップ (`data/backups/`)
- エラー発生時は Windows トースト通知（要 `windows_toast: true`）

---

## セットアップ詳細

### 1. X セッション (auth_token) の取得

各アカウントでブラウザから auth_token と ct0 を取得する必要があります。

1. Firefox で X（Twitter）に**手動ログイン**
2. F12 → ストレージ → クッキー → `x.com`
3. `auth_token` の値をコピー → `data/x_session.json` に保存
4. `ct0` の値も同様にコピー

**セッションファイルの形式:**
```json
{
  "cookies": [
    {
      "name": "auth_token",
      "value": "xxxxxxxxxxxx",
      "domain": ".x.com",
      "path": "/",
      "httpOnly": true,
      "secure": true,
      "sameSite": "None"
    },
    {
      "name": "ct0",
      "value": "yyyyyyyyyyyy",
      "domain": ".x.com",
      "path": "/",
      "httpOnly": false,
      "secure": true,
      "sameSite": "Lax"
    }
  ]
}
```

> **注意:** auth_token は他人に知られるとアカウントを乗っ取られます。  
> `.gitignore` で除外済みですが、取扱いは厳重に。

### 2. ForceBindIP のインストール

各アカウントを異なるネットワークインターフェース（USBテザリング / WiFi）に
バインドするために必要です。

1. `tools/ForceBindIP-1.32.zip` を展開（済み）
2. `tools/ForceBindIP/ForceBindIP64.exe` が存在すれば OK
3. 各アカウントの `config.yaml` で `network_interface` に
   アダプター名を指定（例: `イーサネット`, `Wi-Fi`）

**アダプター名の確認方法:**
```powershell
Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | Format-Table Name, Status
```

### 3. Playwright Firefox のインストール

```bash
pip install -r requirements.txt
playwright install firefox
```

> `playwright install` を忘れるとブラウザ起動に失敗します。

---

## トラブルシューティング

| 症状 | 原因 | 解決策 |
|------|------|--------|
| Firefox が起動しない | Playwright未インストール | `playwright install firefox` を実行 |
| X にログインできない | auth_token が切れている | ブラウザで再ログイン → セッション再取得 |
| `ForceBindIP: ファイルが見つかりません` | ForceBindIP未配置 | `tools/ForceBindIP/` を確認、ZIPを再展開 |
| `[SKIP] 動作時間外` | 深夜（00:00〜08:59） | 09:00〜23:59 の間に実行 |
| `[LIMIT] 日次上限到達` | その垢の1日分終了 | 翌日まで待つ |
| `collected.json が空` | 収集がまだ | `python kensho_collect.py --pages 3` を実行 |
| ログが多すぎる | 定常動作 | 30日以上前のログは自動削除されます |
| ネットワーク不通 | USBテザリング切断 | `daemon.py` が自動再接続を試みます |
| 応募がスキップされる | 応募済み or 日次上限 | `data/collected.json` の `applied` 状態を確認 |

### ログの確認方法

```
logs/2026-06-24/
├── orchestrator_093000.log    # オーケストレーターの動作ログ
├── apply_result_atushi16.json # 応募結果（JSON）
├── daemon_2026-06-24.log      # デーモン死活ログ
└── apply_stderr_atushi16.log  # 応募エラー詳細（障害時）
```

**動作確認のワンライナー:**
```bash
# daemon が動いているか
tasklist /FI "IMAGENAME eq python.exe" 2>nul | findstr python

# 今日の応募結果サマリー
python -c "import json; d=json.load(open('data/daily_counts.json')); print(d)"
```

---

## アーキテクチャ

```
daemon.py (常駐)
  ├── thread_keepalive  (5分おき) → keepalive/checker.py
  │     ネットワークインターフェース監視・自動復旧
  └── thread_orchestrator (15分おき) → orchestrator.py
         ├── 収集 (09:00/13:00/18:00) → scraping/collector.py
         └── 応募 (バッチ時刻) → kensho_apply_single.py → applier.py
                ├── create_browser() → browser.py (指紋偽装)
                ├── check_x_login() → Xログイン確認
                └── apply_for_account() → Like/RT/Follow/Reply
```

各アカウントは ForceBindIP で異なるネットワークインターフェースに
バインドされ、IP分離が保証されます。
