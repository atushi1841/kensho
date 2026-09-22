# t_0f7bdf73 検証エビデンス — worker終端呼出強制ラッパー(設計再定義の成果物確認と回収)

- 日付: 2026-09-22
- タスク: t_0f7bdf73
- 担当: kensho-worker
- 状態: 設計再定義 t_f3ba57cb により worker側ラッパー実装は廃止、実行機構側への委譲+純監視バリデータ新設で解決。本カードは再定義成果の確認と回収。

## 背景

t_0f7bdf73 は「kensho-worker の終端呼出(kanban_complete/block)強制ラッパー」を worker 編集コードとして
実装しようとし、実装対象=ラッパー自身という自己矛盾で protocol_violation 永久ループに陥った
(run 916/917/919/920 が rc=0 clean-exit 未終端で crashed)。設計再定義 t_f3ba57cb(commit 0344a7a)が:

1. worker 側ラッパー実装を廃止 — worker が編集するコードで強制すると自己矛盾で永久ループ
2. 終端呼出強制は実行機構側に既に存在(worker コード非依存 : hermes dispatcher detect_crashed_workers +
   agent/kanban_stop.py nudge)へ委譲
3. kensho 側は読み取り専用の純監視バリデータ scripts/terminal_call_validator.py を新設(行動変更なし)

## verification_evidence

```
$ cd /mnt/d/Project2/kensho
$ git ls-files scripts/terminal_call_validator.py docs/terminal-call-enforcement-redesign-t_f3ba57cb.md reports/t_f3ba57cb_verification.md
  → 3ファイルが git 追跡済み (commit 0344a7a, HEAD main)
$ git log --oneline -3
  → 0344a7a - 3692561 - 31b514c (再設計コミットが HEAD に存在・push済み)
$ python3 scripts/terminal_call_validator.py --json
  → {"blocked_pv_count":0, "incidents_24h":41, "unrecovered_24h":{"t_efc31433":2}, "mode":"readonly_monitor"}
$ python3 scripts/terminal_call_validator.py
  → terminal_call_validator: mode=readonly_monitor / blocked_pv=0 / incidents_24h=41 / unrecovered_24h=2
$ hermes kanban --board kensho-ai-team list --status blocked --json 2>/dev/null | grep -c 'protocol_violation\|未コミット'
  → 1 (t_0f7bdf73 自身が blocked 残留のため。UMBLOCK 後 ready へ回収)
```

## 判定

- 再設計成果(design doc + 純監視バリデータ)は commit 0344a7a で確定・push済み。バリデータは読み取り専用
  (mode=readonly_monitor)で kanban_complete/block を発行しない、常に exit 0。
- 実行時: blocked_pv_count=0(blocked+protocol-violation起因のタスク残留なし)。
- incidents_24h=41 は直近24hの protocol_violation イベント、うち unrecovered は t_efc31433(2件)。
  t_efc31433 は loop_health.sh FINDING2 回帰テストカードで、本スイープで同時 UNBLOCK(20:24)済み
  ⇒ status=ready、再ディスパッチ待ちの過渡状態(再runで回収予定)。blocked 残留ではない。
- 本カード(t_0f7bdf73)自身は設計廃止により手動 UNBLOCK(20:24)で ready 化 → 本 run で回収。

## 引き継ぎ

- worker 側ラッパー実装は設計判断により実施しない(自己矛盾のため)。終端呼出強制は実行機構側に存在。
- kensho 側は scripts/terminal_call_validator.py が watchdog / regression_gates_ledger へ供給する
  独立の監視データ源。7日間 protocol_violation起因 blocked残留 0 件は導入後計測対象(現状 blocked_pv=0)。
