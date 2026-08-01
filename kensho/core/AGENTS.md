# core/ — コア機能モジュール

## 概要
プロジェクト全体で使われる基盤機能。単一責任でシンプルに。

## 構成
| ファイル | 役割 |
|----------|------|
| `config.py` | config.yaml読み込み・バリデーション |
| `encoding.py` | cp932ガード（絵文字→ASCII変換） |
| `logger.py` | ログ出力（日別ファイル） |
| `notifier.py` | Windowsトースト通知 |
| `cleanup.py` | ゾンビプロセス掃除 |

## 重要ルール

### encoding.py
- `guard_stdio()` — 全エントリポイントで必ず最初に呼ぶ
- `cp932_safe(text)` — 絵文字を含む文字列をcp932端末安全に変換
- 絵文字マップ: ✅→[OK], ❌→[NG], ⚠️→[!] など
- Windowsのchcp65001問題対策として必ず使用

### config.py
- 設定ファイルは `config.yaml`（プロジェクトルート）
- `load()` — バリデーション＋デフォルト値補完
- 必須項目不足は `ConfigError` で起動時エラー

### logger.py
- ログは `logs/YYYY-MM-DD/` に日別保存
- 30日以上前のログは自動削除

### cleanup.py
- **ユーザーのFirefoxは絶対にkillしない**（親プロセスがpythonのもののみ対象）
- `taskkill /F /IM firefox.exe` は禁止

## 修正時の注意
- `encoding.py` の変更は全モジュールに影響 — テスト必須
- 各 `__init__.py` は短縮importパス（`from core import config`）対応
- すべての `open()` は `encoding='utf-8'` 必須
