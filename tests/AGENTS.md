# tests/ — テストモジュール

## 概要
pytest + mypy strict mode。現在51テスト、全パス。

## 構成
| ファイル | 役割 |
|----------|------|
| `test_collector.py` | 収集ロジック（deadline抽出9パターン、is_x_url 6パターン） |
| `test_applier.py` | 応募ロジック（稼働時間、リプライ生成、日次カウンター、レート制限、排他ロック） |
| `test_encoding.py` | cp932変換（cp932_safeテスト3件） |
| `test_backup.py` | バックアップユーティリティ |
| `__init__.py` | 空ファイル（パッケージマーカー） |

## テスト実行
```bash
cd /d/Project2/kensho
python -m pytest  # 全テスト
python -m pytest tests/test_collector.py -v  # 特定ファイル
python -m pytest -xvs  # 詳細出力＋最初の失敗で停止
mypy .  # strict mode 0 error
```

## ルール
- pytestの `tmp_path` を使って実際のファイル操作をテスト
- ネットワーク依存のテストはmock必須（httpx等）
- Playwright（Firefox実ブラウザ）はmock — 実際の応募はテストしない
- 新機能を追加したら必ずテストも書く
- mypy strict mode は 0 error を維持

## 修正時の注意
- テストは `D:\Project2\kensho` ルートから実行（相対importのため）
- テスト失敗時はまず他のモジュールの変更を確認
- `test_applier.py` は応募ロジックの動作保証 — 手を抜かない
