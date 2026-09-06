# revenue-worker v44 — 監査lasterr鮮度分類（アラート疲労の恒久対策）

- 実行: 2026-09-07 02:45–03:1x JST（nightly-worker cron 5e8ec4984bba）
- タスク: t_53b0793a（critic_proposal_2026-09-07-v44、idempotency-key critic-20260907-v44-lasterr01）
- health JSON: score=95 / ready=0 / blocked=0 / priority=new_proposals
  → readyタスク無しの為、直前の自走監査で実測検出した構造的欠陥を自発タスク化して実装

## 事象（実測エビデンス）

`scripts/kensho-noagent-job-audit.sh`（06:30 Telegram監査 a85cf2d361cf）が毎日 FAIL=2 を報告:

| job | last_status | last_run_at | script mtime | 実態 |
|-----|-------------|-------------|--------------|------|
| ce22c907d66d kanban-ready-deprecate-nightly | error | 9/6 04:00 | 9/6 23:46 | Script not found は v32 で配置済み。9/7 04:00 で自己解消予定 |
| c0e8e4d76933 kensho-dataset-weekly-update | error | 8/31 14:46 (156h前) | 9/7 01:10 | 旧playwright版失敗はCDP方式へ書き換え済み。9/7 10:00 で再検証予定 |

`last_status == "error"` を無条件FAILにしていたため、**既に手当て済みの死んだエラーを毎日通知**し続ける。
SREの alert fatigue 原則（スキルai-team-improvement「skip_fastとmonitorゲート」節と同じ思想）に違反し、
本当に新しい障害が起きたときノイズに埋もれる。

## 実装

変更ファイル: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-noagent-job-audit.sh`
（`~/.hermes/scripts/kensho-noagent-job-audit.sh` は同実体へのsymlink、06:30 cronが実行するのはいずれも同じ）

`classify_lasterr(j, script_path)` を追加し、error を3分類:

| verdict | 条件 | 扱い |
|---------|------|------|
| fresh | last_run_at が script mtime より後 かつ 経過 ≤ STALE_HOURS(48h) | **FAIL**（実対応必要） |
| pending | script mtime > last_run_at（修正が失敗より後） | stderr NOTE のみ（次tickで再検証待ち） |
| stale | 経過 > 48h | stderr NOTE のみ |

自己修正性: 次回cron実行で last_run_at > mtime になるため、**同じエラーが再発すれば fresh としてFAIL復帰**する。抑圧は高々1サイクル。
`AUDIT_STALE_HOURS` 環境変数で閾値調整可。last_run_at欠損/パース不能は安全側（fresh=FAIL）。
`p = None` 初期化をループ先頭に追加（no-script-field時の前ループ残存参照バグ防止）。

## 自己レビュー要点

- 事前コピー /tmp/audit_pre_v44.sh との差分 = +53/-1 のみ、意図した変更だけ
- import追加なし（datetime/os/jsonは既存）、閾値は環境変数で上書き可能
- APIキー等の機密は出力しない（job id/nameのみ）
- 既存チェック（outside/missing/dryrun/deadprofile/dupname）は不変。dupname FAIL=0 は v34 FIX A（7c8cb6584502 pause済み）を再確認
- 残課題: kensho-revenue-worker プロファイル内の旧コピーがdrift（162行差）。同プロファイルcronは死んでいる（v33実測済み）ため無害だが、監査引数で明示指定すると誤作動しうる → 申し送り（notepad）

## verification_evidence

$ bash -n /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-noagent-job-audit.sh → SYNTAX OK

$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-noagent-job-audit.sh
SUMMARY profile=kensho-sweeps active=25 fail=0 threshold=2 gw=kensho-sweeps,tai deadprofile_profiles=0 → 従来 fail=2 が fail=0 へ、exit=0

$ 同上 stderr
NOTE ce22c907d66d::kanban-ready-deprecate-nightly — lasterr-pending: script mtime +19.8h after error → pending分類実証
NOTE c0e8e4d76933::kensho-dataset-weekly-update — lasterr-pending: script mtime +154.4h after error → pending分類実証

$ bash kensho-noagent-job-audit.sh v44test（fixture: fresh5h / stale100h / pending30h+新mtime の3error注入）
SUMMARY profile=v44test active=3 fail=1 → fresh001 のみ FAIL、pend001/stale001 は NOTE → 3分類すべて正しく動作（誤suppress無しを証明）

$ fixture撤去後 冪等再実行 → fail=0 同一出力（06:30配信は threshold=2 未満でstdoutサイレント=Telegram誤通知消滅）
