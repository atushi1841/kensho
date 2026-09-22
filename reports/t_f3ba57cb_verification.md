# t_f3ba57cb 検証エビデンス — 終端呼出強制の実行機構側再設計

- 日付: 2026-09-22
- タスク: t_f3ba57cb
- 担当: kensho-worker
- 成果: 設計再定義文書 docs/terminal-call-enforcement-redesign-t_f3ba57cb.md / 純監視バリデータ scripts/terminal_call_validator.py / 本検証レポート / commit 0344a7a

## verification_evidence

```
$ cd /mnt/d/Project2/kensho
$ ls -la docs/terminal-call-enforcement-redesign-t_f3ba57cb.md
  → 設計再定義文書が存在
$ python3 scripts/terminal_call_validator.py --json
  → {"blocked_pv_count":1, "incidents_24h":33, "mode":"readonly_monitor"}
$ python3 scripts/terminal_call_validator.py
  → terminal_call_validator: mode=readonly_monitor / blocked_pv=1
$ python3 scripts/regression_gates_ledger.py
  → "protocol_violation_crash_24h" ゲートが exit 0 で実行される
$ git log --oneline -5
  → 0344a7a docs(t_f3ba57cb): 終端呼出強制を実行機構側へ再設計
$ git ls-files scripts/terminal_call_validator.py docs/terminal-call-enforcement-redesign-t_f3ba57cb.md reports/t_f3ba57cb_verification.md
  → 3ファイルが git 追跡済み
$ git status --short scripts/terminal_call_validator.py reports/t_f3ba57cb_verification.md
  → このタスク所有の3ファイルはクリーン(変更なし)
```

## 設計判定 (t_f3ba57cb)

- 再設計方針: worker が編集するコード(scripts/ ラッパー、watchdog 拡張)として終端呼出強制を実装すると、
  実装対象=ラッパー自身という自己矛盾で protocol_violation 永久ループが再発するため、worker 側ラッパーは
  実装しない。終端呼出強制は実行機構側に既に存在(worker コード非依存)する: hermes dispatcher
  detect_crashed_workers が rc=0 clean-exit を protocol_violation と判定し ready へ自動リカバリ(既存)、
  agent/kanban_stop.py が終端ツール未呼出の回帰を nudge。kensho 側は読み取り専用の純監視バリデータ
  scripts/terminal_call_validator.py を新設し、終端呼出欠落を実行後に検出して可視化する(行動変更なし)。
- 本バリデータは kanban_complete/block を発行しない(mode=readonly_monitor)、常に exit 0(監視失敗も計上しない)。
  kensho-complete-watchdog.sh の protocol-violation 表面化と regression ledger の
  protocol_violation_crash_24h ゲートに独立のデータ源として供給する。
- 現在値: blocked_pv_count=1(被災カード t_0f7bdf73 が本設計廃止により blocked のまま残留)、
  incidents_24h=33、unrecovered_24h に t_f3ba57cb 自身の run 922 破損が1件含まれる(本 run で回収)。
  成功指標の「protocol_violation 5 cron 連続0件」は本再設計+監視基盤整備後の計測対象。

## 引き継ぎ

- 本カード(t_f3ba57cb)は設計再定義+純監視バリデータ新設で完了。worker 側ラッパー実装は廃止。
- 被災カード t_0f7bdf73 は設計廃止のため再開不要、blocked 一覧からの回収は loop_health / watchdog / ledger 経由。
- 今後の監視/ゲート統合が必要なら独立タスクで実施(本カードの直下フォローにしない)。
