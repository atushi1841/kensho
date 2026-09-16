# critic v169 (t_83759a2e) — 応募停止の早期検知（検知層のみ）verification report

- タスク: t_83759a2e / assignee: kensho-revenue-worker
- 実測日時: 2026-09-17 05:30〜05:47 (JST)
- 目的: 応募パイプライン停止(kensho-auto-apply.sh:108 flock -c 内 pgrep 自己マッチ誤発火)の**再発防止「検知・検査層」**を t_83759a2e として追加。応募ロジック/パイプライン挙動は一切変更しない（制約順守）。

## t_83759a2e の成果物

1. `scripts/kensho-apply-stall-check.sh` — 稼働窓(09-23)内に当日/履歴ログの「完了」行が閾値(既定120分)を超えて増えない＝応募停止を検知し、1回だけ通知文を出力。平常時は [SILENT]（出力なし）。`--dry-run` は判定のみ表示し sentinel を書かない。
2. `scripts/check_spawn_pgrep_selfmatch.py` — kensho-auto-apply.sh 内の `pgrep -f` が `flock -c "..."` の内側で、concrete 形（`[x]`クラス展開後）の連続部分文字列が flock ブロック文字列に出現する＝自己マッチパターンを検出し exit 1（回帰ゲート）。
3. cron `kensho-apply-stall-check` (job 6b6622e183c8): cron 式 `0,30 9-23 * * *`, no_agent watchdog, `deliver=telegram`, script=kensho-apply-stall-check.sh（profile scripts 実体コピー）。stdout 空=配信なし、停止時にのみ通知文配信。

## t_83759a2e 適用例

- 参考: 実際の kensho-auto-apply.sh 修正（L108/L109）は別カード t_9f37e5e3 の要ユーザーGO 対象。本例 t_83759a2e は検知層のみで修正を伴わない。

## verification_evidence

検証① t_83759a2e 静的検査（現行の壊れた行 → exit 1）

$ cd /mnt/d/Project2/kensho
$ python3 scripts/check_spawn_pgrep_selfmatch.py /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-auto-apply.sh; echo "exit=$?"
FAIL: spawn スクリプトに flock -c 内で自己マッチしうる pgrep を検出（2件）
  .../kensho-auto-apply.sh:108  pattern='kensho/orchestrator.py --account $acct'  concrete='kensho/orchestrator.py --account $acct'
  .../kensho-auto-apply.sh:109  pattern='kensho/orchestrator.py --account'  concrete='kensho/orchestrator.py --account'
対処: パターンを `[k]ensho` 等の文字クラス逃避形（concrete が flock ブロック文字列に
      連続部分文字列として現れない形）へ書き換えること。
exit=1

検証② t_83759a2e 静的検査（修正済み＝案②（t_9f37e5e3基準）：flock 内の冗長 pgrep ガード削除 → exit 0）

$ python3 /tmp/make_fixb.py          # 実体から L108/L109 ガード行を除去した FIXB を生成
removed:
  L108: if pgrep -f 'kensho/orchestrator.py --account $acct' >/dev/null 2>&1; then exit ...
  L109: if [ \\$(pgrep -cf 'kensho/orchestrator.py --account' 2>/dev/null || echo 0) -ge ...
$ python3 scripts/check_spawn_pgrep_selfmatch.py /tmp/kensho-auto-apply-FIXB.sh; echo "exit=$?"
OK: /tmp/kensho-auto-apply-FIXB.sh の flock -c 領域に自己マッチする pgrep は検出されません
exit=0

注記（t_83759a2e 設計判断）: 案①の `[k]ensho` を L108 に適用すると concrete は flock ブロック内に（オーケストレータ実行行の `--account '$acct'` が account を単クォートするため）出現せず検査は L108 を通過。ただし L109(カウント用)は account なしのため concrete が実行行に漏れ、本検査は L109 を継続検出する（=実デプロイでも flock 自己カウントで上限ガードに残る正しい判定 managed by t_83759a2e）。完全修正には L109 もエスケープ/削除が要る。

検証③ t_83759a2e 稼働窓外 → SILENT exit 0（平常時 通知0件 =偽陽性なし）

$ bash scripts/kensho-apply-stall-check.sh --dry-run; echo "exit=$?"
SILENT: 稼働窓外 (H=5)
exit=0

検証④ t_83759a2e 稼働窓内・停止(stall>120分) → NOTIFY 通知文出力

$ KENSO_STALL_HOUR=10 bash scripts/kensho-apply-stall-check.sh --dry-run; echo "exit=$?"
NOTIFY-STAGE: stall=1795min >= 120min
[Kensho] 応募停止検知: 1795分「完了」行なし (今日0件, src=/mnt/d/Project2/kensho/logs/auto_20260915.log)
exit=0

検証⑤ t_83759a2e 稼働窓内・直近完了あり(stall<120分) → SILENT（偽陽性なし）

$ KENSO_STALL_HOUR=10 KENSO_STALL_LOGDIR=/tmp/stall_fake/logs bash scripts/kensho-apply-stall-check.sh --dry-run; echo "exit=$?"
SILENT: 稼働中 (stall=0min, 完了=1)
exit=0

検証⑥ t_83759a2e 送出は停止エピソード毎に1回（sentinel）— 実run1回目は通知、2回目は SILENT

$ KENSO_STALL_HOUR=10 KENSO_STALL_SENTINEL=/tmp/stall_test2.sent bash scripts/kensho-apply-stall-check.sh; echo "exit=$? sent=$(cat /tmp/stall_test2.sent 2>/dev/null)"
[Kensho] 応募停止検知: 1797分「完了」行なし (今日0件, src=/mnt/d/Project2/kensho/logs/auto_20260915.log)
exit=0 sent=1789483524
$ KENSO_STALL_HOUR=10 KENSO_STALL_SENTINEL=/tmp/stall_test2.sent bash scripts/kensho-apply-stall-check.sh; echo "exit=$?"
exit=0        # stdout 空（skip: 同一エピソード通知済み）

検証⑦ t_83759a2e cron 登録（job 6b6622e183c8）— schedule `0,30 9-23 * * *`, no_agent, deliver=telegram

## 残事項（t_83759a2e）
- gateway 未起動のため cron は「保存済み・未発火」。通知配信を有効化するには `hermes gateway start`（または常駐ゲートウェイ）が必要。
- 実際の kensho-auto-apply.sh 修正（L108/L109 消去 or 実行行限定パターン化）は別カード t_9f37e5e3 の要ユーザーGO 対象。本 t_83759a2e は検知層のみで変更しない。
