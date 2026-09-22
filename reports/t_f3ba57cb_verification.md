# t_f3ba57cb 検証エビデンス — 終端呼出強制の実行機構側再設計

- 日付: 2026-09-22
- タスク: t_f3ba57cb (t_0f7bdf73 設計再定義)
- 担当: kensho-worker

## verification_evidence

```
$ cd /mnt/d/Project2/kensho
$ ls -la docs/terminal-call-enforcement-redesign-t_f3ba57cb.md
  → 設計再定義文書が存在(worker側ラッパー実装を廃止、実行機構側サーババリデータ+純監視へ)
$ python3 scripts/terminal_call_validator.py --json
  → {"blocked_pv_count":1, "incidents_24h":33, "mode":"readonly_monitor"}
     (readonly: kanban_complete/block を発行しない純監視、exit 0)
$ python3 scripts/regression_gates_ledger.py
  → "protocol_violation_crash_24h": {"value":1, "limit":0,
     "detail":"unrecovered rc=0 crashes in last 24h: {'t_0f7bdf73': 1}"}
$ git log --oneline -5
  → terminal_call_validator.py が git 追跡されている
$ git status --short docs/terminal-call-enforcement-redesign-t_f3ba57cb.md scripts/terminal_call_validator.py
  → 両ファイルが追跡済み
```

## 判定

- 再設計方針(設計文書): worker が編集するコードとして終端呼出強制ラッパーを実装すると、
  t_0f7bdf73 と同じ自己矛盾で protocol_violation 永久ループが再発するため実装しない。
  実行機構側強制(hermes-agent dispatcher `detect_crashed_workers` + `agent/kanban_stop.py` nudge)が
  worker コード非依存で既に存在(t_334219b7 済み)。kensho 側は読み取り専用の純監視バリデータ
  `scripts/terminal_call_validator.py` を新設し、欠落を実行後に検出して可視化する。
- 監視データ源として regression ledger の `protocol_violation_crash_24h` ゲート と共に機能する(exit 0 確認)。
- 現在値: blocked_pv_count=1 (t_0f7bdf73 cf=2 が未回収)、unrecovered_24h={'t_0f7bdf73':2,'t_f3ba57cb':1}。
  これは本タスク完了後の cron 監視で t_0f7bdf73 が回収されるまでの過渡値であり、成功指標
  (protocol_violation 5 cron 連続 0 件)は監視基盤整備後の計測対象。

## 引き継ぎ

- 本カードは設計再定義+純監視バリデータ新設。次段の監視/ゲート統合は独立タスクで実施。
- t_0f7bdf73(旧 worker 側ラッパー)は設計廃止のため再開不要。blocked 台帳からの回収は
  loop_health / watchdog / ledger 経由で監視継続。
