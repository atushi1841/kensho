# Kensho 稼働サマリー GitHub自動同期 — cron 設定案

**目的**: 毎日 23:55 に `kensho_github_sync.py` を実行し、当日の稼働サマリー
（実行・応募・収集・AIチーム完了タスク・収益・異常）を `docs/daily_reports/YYYY-MM-DD.md`
として生成し、GitHub `atushi1841/kensho` に push する。

## crontab に追加する1行（案）

```cron
# Kensho 稼働サマリー GitHub自動同期 (毎日23:55)
55 23 * * * /mnt/d/Project2/kensho/scripts/kensho_github_sync.sh >> /mnt/d/Project2/kensho/logs/github_sync_cron.log 2>&1
```

※ 既存cronの終盤（23:55時点で他の日次ジョブと衝突しない時間帯）に配置推奨。
23:55 は現在の crontab に競合ジョブが無いことを確認済み（23時台は未使用）。

## インストール手順

```bash
chmod +x /mnt/d/Project2/kensho/scripts/kensho_github_sync.sh
crontab -e   # 上記1行を追記
```

## 前提条件

1. **GitHub 認証**: `git push` に HTTPS 認証（credential helper / PAT / SSH のいずれか）。
   現在 `origin config user.name=atushi, user.email=atushi1841@gmail.com` で push 可能な状態。
2. **依存**: Python3 標準ライブラリのみ（sqlite3, json, re, subprocess — 追加インストール不要）。
3. リポジトリ: `/mnt/d/Project2/kensho` が git clone 済みで `.git` が存在。

## 動作・安全策

- **対象ファイルのみ commit**: `git add -- docs/daily_reports/<date>.md` で該当ファイルのみ
  ステージし、他ワークツリーの変更（data/*, reports/* など多数の未コミット変更）を巻き込まない。
- **無駄commit防止**: 既に同一内容のレポートが存在すればスキップ。
- **差分なしは正常**: commit 時に "nothing to commit" ならエラー扱いせず成功として扱う。
- **push 失敗時**: ローカルにコミットを残し exit code で通知。commit は残留するので
  次回起動時は `git add` 対象ファイルが更新された場合のみ再コミットされる。

## 検証

- `python3 kensho_github_sync.py --dry-run --date 2026-09-22` → レポート生成を確認済み
  （orchestrator 168回, 応募成功129/エラー18, 収集1106件, AI完了6タスク を実データで反映）
- 実 push: `python3 kensho_github_sync.py --date <今日>` で1コミット生成を確認済み。

## 手動実行（任意）

```bash
# 生成のみ
python3 kensho_github_sync.py --dry-run
# 生成＋GitHub push
python3 kensho_github_sync.py
# 過去日
python3 kensho_github_sync.py --date 2026-09-21
```
