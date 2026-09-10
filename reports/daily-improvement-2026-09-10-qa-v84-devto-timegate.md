# QA v84 — t_4e88dfeb devto weekly pipeline 9/14一次実行検証のタイムゲート設定（2026-09-10）

## 目的
critic v83由来の最終受け入れタスク t_4e88dfeb（devto_weekly_pipeline.py repo修復 fbf755a に基づく
cron d538be4f5549 の初回実実行 = 2026-09-14 12:00 JST の検証）を、9/14まで待機（scheduled維持）し、
時刻到達後に自動で検証セッションへ戻す仕組みの実装・実測記録。

## プレフライト実測（全PASS）
- `git ls-files | grep -c devto_weekly_pipeline.py` = **1**（HEADで追跡済み、fbf755aが履歴に存在）
- cronジョブ d538be4f5549（devto-weekly-seo-post、**kensho-sweepsプロファイル**）:
  enabled=true / state=scheduled / expr=`0 12 * * 1` / next_run_at=2026-09-14T12:00:00+09:00 / last_run_at=null（初回実行待ち）
- kensho-sweeps gateway稼働中（PID 474）→ 9/14定時発火見込み
- **落とし穴記録**: プロファイル横断で `hermes cron list` を叩くと "No scheduled jobs" と表示され、
  検証コマンドが偽阴性になる（cron状態は profiles/kensho-sweeps/cron/jobs.json と output/ が権威）。
  → 9/14検証セッションへ申し送り済み（カードコメント #551）。

## タイムゲート機構（WSL原生crontab、gateway非依存）
- `scheduled` ステータスは自動ディスパッチされない（hermes_cli/kanban_db.py schedule_task のdocstringで実証:
  外部cron/人手が unblock_task を呼ぶまで待機）。
- 起動用ワンショット: `20 12 14-20 9 * wake_kanban_t_4e88dfeb.sh`
  - 9/14 12:20 JST（devto実行窓+10分バッファ）に `hermes kanban unblock t_4e88dfeb` → QAセッション再ディスパッチ
  - 実行後 self-remove。9/15以降もscheduledのままだった場合のリトライ窓（9/14–9/20 12:20）付き
  - statusがscheduledでなくなれば即自己除去（二重起動防止）
- スクリプトのゲート判定は9/10に自走テスト実施: 「before fire gate, keeping entry」をログで確認済み。

## 9/14検証セッションへの申し送り
1. jobs.json の last_run_at ≥ 2026-09-14T12:00 かつ last_run_status=success、cron output の exit_code=0 / Error数=0
2. dev.to draft count ≥ 1（devto_check_drafts.py 方式、DEVTO_API_KEYは.envから、値の出力禁止）
3. `git ls-files | grep -c devto_weekly_pipeline.py == 1`（再度untrackedならHIGH回帰としてエスカレーション）
4. API/token系エラーなら [USER-ACTION-REQUIRED]（Dev.to APIキーローテーション）でblock

## 方針遵守
- コード変更なし（検証・記録・スケジュール設定のみ）。BOT検出回避観点: 本タスクはdev.to APIのみでX操作なし、キー値の非出力を申し送りに明記。
