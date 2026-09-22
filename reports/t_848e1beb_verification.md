# kensho-worker終端呼出強制 — 実装・検証レポート

## 概要 (t_848e1beb)
- 成果物: kensho-worker の終端 kanban 呼出強制(protocol_violation再発防止)。2段構え。
  - [1] プロンプト自己チェック: kensho-worker SOUL.md に「rc=0でも complete/block 未呼出なら失敗扱い」の絶対ルールを明記(前run 895 で追加済み、本runで有効性確認)。
  - [2] 監視の表面化: `scripts/kensho-complete-watchdog.sh` に protocol_violation 被災(blocked)タスクの自動スキャンを追加。`[protocol-violation-blocked]` コメントで unblock 再開を促す。cron `*/30 * * * * ... --apply` ですでに定期実行中。

## 背景
- dispatcher は rc=0 で complete/block を呼ばずに終了した worker run を既に protocol_violation として自動失敗扱いする(実績: t_3aa5365c run 884/886/887/889、t_848e1beb run 893/894/895)。すなわち「wrapper強制」は dispatcher 側で既存。真のギャップは worker がその規約を知らない点 → プロンプト明記で解消。
- さらに、PV 被災タスクは status=blocked で沈黙放置され、成果完了済みなのに再開されない。既存の runningハング検知(complete-watchdogの本体)は status=blocked を捕捉できないため、PVスキャンを別途追加した。

## 成功指標との対応
- 本カード自身の終端呼出: 本run終端で kanban_complete を発行(past 3 runs の protocol_violation ストリークを断つ=ストリーク実証)。
- t_3aa5365c: blocked(cf=2)。本runでは unblock 手段が無いため、watchdog が自動で表面化コメントを投稿し、unblock 後の再 dispatch 時には更新済み SOUL.md が有効 → complete/block 呼出あり終了を見込む(検証は次dispatchに委譲)。
- 新規 PV ブロック 0 件/7日: SOUL.md ルール適用後の新 dispatch の監視で確認(将来評価)。

## verification_evidence
- `bash -n /mnt/d/Project2/kensho/scripts/kensho-complete-watchdog.sh``
- → `SYNTAX OK`
- `bash /mnt/d/Project2/kensho/scripts/kensho-complete-watchdog.sh --dry-run --verbose`
- → 出力: `protocol-violation: t_3aa5365c|protocol_violation(cf=2)` (PV被災タスクを正しく検出)
- → 出口: `exit=0` (dry-run はコメント投稿抑制のまま対象表示・SILENT 規約維持)
- `grep -n '終端kanban呼出の鉄則' /home/atushi/.hermes/profiles/kensho-worker/SOUL.md`(ルール実在確認)
- → 出力: `3:# 終端kanban呼出の鉄則（t_848e1beb / 2026-09-22 / 絶対ルール・protocol_violation再発防止）` ほか 4-7 行に「rc=0でもcomplete/block未呼出なら失敗扱い」「最終レスポンス前の自己チェック」「失敗時はkanban_blockで終端」を明記
- `python3 /tmp/check_pv.py`(kanban.db 直接参照)
- → 出力: `protocol violations blocked: 1` + `('t_3aa5365c','blocked',2,...)` (被災タスク台帳と一致)
- 同期確認: `/home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/kensho-complete-watchdog.sh` は repo copy への symlink → 1 file patch で cron 適用も反映。
- 変更多くある working tree から対象 2 file(scripts/kensho-complete-watchdog.sh + 本レポート)のみ `git add` して commit。data/reports churn は非接触。

## changed_files
- /mnt/d/Project2/kensho/scripts/kensho-complete-watchdog.sh(PV被災タスク表面化追加)
- /mnt/d/Project2/kensho/reports/t_848e1beb_verification.md(本レポート)
- /home/atushi/.hermes/profiles/kensho-worker/SOUL.md(前run 895で追加、本run検証)
