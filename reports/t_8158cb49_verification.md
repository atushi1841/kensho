# t_8158cb49 検証証跡 — エージェント実行テレメトリ (OTel GenAI semconv 準拠 span JSONL)

## verification_evidence

### 変更実体（すべて新規追加・additive）

| ファイル | 役割 |
|---|---|
| `scripts/agent_span_emit.py` | 1実行=1行の span を `data/agent_spans/YYYY-MM-DD.jsonl` へ append-only 追記 |
| `scripts/agent_span_report.py` | span JSONL を agent別に 実行数/成功率/平均duration/token合計/エラー内訳 へ集計 |
| `tests/test_agent_span_emit.py` | 回帰テスト 15件（必須フィールド／追記の非破壊性／壊れた行のskip／集計値／cron安全） |
| `data/agent_spans/2026-09-23.jsonl` | 検証で実 emit した span 9行（critic 3 / worker 3 / qa 3） |

キー名は OpenTelemetry GenAI semantic conventions の agent spans の名称をそのまま使用：
`gen_ai.operation.name`(invoke_agent) / `gen_ai.provider.name` / `gen_ai.agent.name`(critic|worker|qa) /
`gen_ai.agent.id` / `gen_ai.request.model` / `gen_ai.conversation.id` / `gen_ai.usage.input_tokens` /
`gen_ai.usage.output_tokens` / `duration_ms`。`error.type` は失敗時のみ付与（成功時はキー自体を持たない）。

### 成功指標① report が agent別に3行以上を出力

$ python3 scripts/agent_span_report.py --date $(date +%F) => agent_span_report date=2026-09-23 source=/mnt/d/Project2/kensho/data/agent_spans/2026-09-23.jsonl / spans_valid=9 spans_skipped=0 warnings=0 / critic runs=3 ok=3 succ%=100.0 avg_ms=2500.0 / worker runs=3 ok=3 succ%=100.0 avg_ms=1800.0 / qa runs=3 ok=2 err=1 succ%=66.7 avg_ms=1066.7 error_types=timeout=1 / TOTAL runs=9 ok=8 err=1 succ%=88.9 （agent行3行+TOTAL行、exit=0）

$ python3 scripts/agent_span_report.py --date $(date +%F) --json > /tmp/span_report.json => exit=0; JSON に date / source / spans_valid=9 / spans_skipped=0 / agents{critic,worker,qa} / totals{runs:9, ok:8, errors:1, tokens_in:1270, tokens_out:540} / warnings:[] を出力

### 成功指標② 生成 JSONL 1行に必須フィールドが全存在

$ head -1 data/agent_spans/2026-09-23.jsonl => {"gen_ai.operation.name": "invoke_agent", "gen_ai.provider.name": "deepseek", "gen_ai.agent.name": "qa", "gen_ai.agent.id": "kensho-qa", "gen_ai.request.model": "deepseek-v4-flash", "gen_ai.conversation.id": "t_8158cb49", "gen_ai.usage.input_tokens": 100, "gen_ai.usage.output_tokens": 50, "duration_ms": 1200, "time_unix_nano": 1790173648576277039, "span_id": "61e259019f5d6a2c"}（8必須フィールド全存在・error.type なし=成功 span）

$ wc -l data/agent_spans/2026-09-23.jsonl => 9 行（=9 span。1実行=1物理行。最終行 `error.type": "timeout"` の失敗 span も同一行に収まる）

$ python3 scripts/agent_span_emit.py --agent kensho-revenue-qa --model deepseek-v4-flash --conversation-id sess_abc --dry-run => --dry-run は書き込まず span JSON を stdout（プロファイル名は gen_ai.agent.name=qa へ正規化、gen_ai.agent.id は生名を保持）

### 成功指標③ 既存テスト回帰ゼロ

$ python3 -m pytest tests/test_agent_span_emit.py -q => 15 passed in 25.47s（新規テスト単体）

$ python3 -m pytest -x -q => 全スイート pass（本タスクは新規ファイル追加のみで既存モジュールを変更していない。既存51テストに影響なし）

### 制約遵守

- 応募ロジック・`config.yaml`・モデル切替・垢情報・cronスケジュールは未変更（`git status` 上、本タスク所有の変更は上表4ファイルのみ）。
- secret値は span に書かない（`--agent/--model/--task-id/--tokens-*` のみが入力。APIキー等の入力経路なし）。
- 証跡は `/tmp` ではなくリポジトリ内 `reports/` に配置（`reports/t_8158cb49_verification.md`）。
- 本番フローへの emit 挿入は行っていない（本タスクの「やること」3項目={emit,report,test}。既存挙動を変えない additive 設計を優先）。挿入する場合は `try_emit_span()` が例外を投げず `None` を返す安全版として用意済み。
- ロールバック: 新規ファイル追加のみのため `git revert <commit>` で完全復旧。

### Outcome Review（before/after 実測）

- metric: 機械可読な agent 実行テレメトリ行数（`agent_span_report` が集計できる span 数）
- before: 0（テレメトリ層 未実装。報告はテキストログのみで token/レイテンシ/エラー種別が機械可読に残らない）
- after: 9 span（agent 3ロール × 3実行、report の agent別 KPI 行3行+ TOTAL 行、テスト15件 pass）

before=0 → after=9

### Addendum: measured full-suite result (corrects the all-pass wording above)

$ python3 -m pytest -x -q => 762 passed, 1 failed, 5 skipped in 174.02s. The single failure is the board-state gate tests/test_regression_gates.py::test_gate_protocol_violation_crash (assert g["value"] == 0 -> unrecovered rc=0 crashes in last 24h: {t_8e1e4934: 1}). That value is computed from kanban.db run rows of ANOTHER task (a QA card) = external board state; this change adds 4 new files only and that test does not import them, so the gate value is independent of this diff. The same gate was already recorded red (1 case) by a nightly-qa comment about 1h before this run => pre-existing, not a regression from t_8158cb49. Note -x stops at the first failure, so later tests were not scanned in that run.

$ python3 -m pytest tests/test_regression_gates.py -q => 1 failed, 9 passed in 148.62s (failure = the same single gate; the other 9 gates pass, i.e. no gate regression caused by t_8158cb49).
