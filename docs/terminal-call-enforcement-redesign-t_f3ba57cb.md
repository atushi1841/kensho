# t_f3ba57cb 設計再定義: 終端呼出強制を worker 側コードでなく実行機構側へ

- 日付: 2026-09-22
- 元タスク: t_0f7bdf73 (worker終端呼出強制ラッパー実装) → protocol_violation 4回連続で crashed → gave_up → blocked
- 本タスク: t_f3ba57cb (設計再定義)

## 背景 / エビデンス

t_0f7bdf73 は「kensho-worker の終端呼出(kanban_complete / kanban_block)強制ラッパー」を
worker 編集コード(scripts/ のラッパー或いは kensho-complete-watchdog.sh 拡張)として実装しようとした。
しかし:

1. 実装対象がまさに当該ラッパー自身である。
2. worker は「終端ツールを呼んで(呼ばないと)rc=0 で静かに終える」ことがプロトコル違反の対象であり、
   このカードを worker が編集する行為自体が、編集対象コードの機能(終端呼出強制)を検証する前に
   プロトコル違反を発火してしまう。
3. つまり「強制ラッパーを worker 側コードとして実装して検証する」タスクは、テスト実行の度に
   ラッパー自身の検証不足で protocol_violation になり、失敗 → 再試行の永久ループに陥る。

これが実測で確認された:
- t_0f7bdf73 の task_events に protocol_violation が4件(run 916/917/919/920)。
- 最終 status=blocked, consecutive_failures=2。
- 2026-09-22 QA 観測で blocked 滞留を確認。

## 設計方針 (再定義)

終端呼出強制を worker 編集コードから**実行機構側**へ移す。

### (1) 実行機構側のサーババリデータで強制 — 既に存在、worker コード非依存

hermes-agent 側には既にサーバ(dispatcher)側強制がある(worker コードでなく実行機構実装):

- `detect_crashed_workers` (hermes_cli/kanban_db.py): worker が rc=0 で kanban_complete/block 未呼出のまま
  clean-exit した場合、`_classify_worker_exit()` == "clean_exit" を検出して protocol_violation イベント化し、
  task を ready へ自動リカバリ。t_334219b7 で「clean-exit protocol_violation は failure 計上・ブレーカー
  発動せず、常に ready へ自動リカバリー」へ一本化済み。
- `agent/kanban_stop.py` + conversation_loop の nudge: 終端ツール未呼出で finish_reason=stop しようとする
  回帰に bounded synthetic nudge を注入して終端ツール呼出を促す。

これらは worker が編集する kensho code ではない — 実行機構(hermes)側の実装であり、worker 自身が
この強制の対象であっても自己矛盾しない(編集対象が自分のカードロジックでないため)。

### (2) kensho 側は「純監視」に徹する — 行動変更なしの可視化

t_0f7bdf73 の失敗時代替案(dispatcher 側フック実装が不可能の場合)に沿い、kensho 側は worker を
誘導・強制するコードを書かず、**終端呼出欠落を実行後に検出して可視化する監視バリデータ**を新設した:

- `scripts/terminal_call_validator.py` — 読み取り専用。blocked+protocol-violation 起因のタスクと
  直近24hの protocol_violation 発生(未回収分類)を JSON/短文で report。decode は exit 0 (純監視なので
  失敗も計上しない)。kanban_complete/block は発行しない(mode=readonly_monitor)。
- これは watchdog (kensho-complete-watchdog.sh の protocol-violation 表面化) と
  regression_gates_ledger.py の `protocol_violation_crash_24h` ゲートに供給する独立のデータ源。

### なぜ worker 側ラッパーを「実装しない」か

- 実装しても worker がそれを編集する限り t_0f7bdf73 と同じ自己矛盾ループが再発する。
- 実行機構側強制(dispatcher detect + kanban_stop nudge)が既に worker コード非依存で存在する以上、
  worker 側に重複実装を足す価値が無い。
- loop_health.sh / watchdog / regression ledger による監視で、欠落を沈黙のまま放置しない既存経路が有る。

## 成功指標

- 再設計タスク完了後、protocol_violation インシデントが 5 cron 連続 0 件。
- loop_health.sh の blocked 一覧に t_0f7bdf73 が無い。
- 新設サーバ側バリデータ(scripts/terminal_call_validator.py)が git 追跡されている。

## 検証コマンド

- `bash scripts/terminal_call_validator.py --json` → blocked_pv_count が0ならOK
- `python3 scripts/regression_gates_ledger.py` → `protocol_violation_crash_24h.value` が0ならOK
- `git log --oneline -5` → terminal_call_validator.py が追跡されている

## 引き継ぎ

- 本カードは設計再定義。実装(worker 側ラッパー)はt_0f7bdf73 の方式を廃止したため行わない。
- 次段の監視/ゲート統合が必要なら独立タスクで実施(本カードではバリデータ新設+設計文書のみ)。
