# t_f5f3bc95 検証証跡 — protocol_violation_crash_24h 回収判定（v167）

タスク: t_f5f3bc95（QA run524起票・高）
実行者: kensho-revenue-worker（nightly-worker run57以降）
実施日時: 2026-09-16 16:0x〜16:2x JST

## 変更概要

- `scripts/regression_gates_ledger.py`: `evaluate_crash_recovery(con, cutoff)` 純関数を分離。
  crash後同一タスクの再runあり or タスクdone/archived終端 → 回収済みとして除外、
  未回収（crashが最後runのまま放置）のみ value 計上。
- `tests/test_regression_gates.py::test_gate_protocol_violation_crash`: docstring・メッセージ改訂（未回収语义）。
- `tests/test_crash_recovery_gate_v167.py`: 合成sqlite fixtureで回収判定4パターンをユニットテスト新規。
- 副産物: `tests/test_non_api_revenue_hunter_gate.py::test_cap_three_creates` をv162 guard実ボード走査の
  モックで決定論化（t_37c0fafa guard導入以来、実ボード状態依存で不安定化していた）。

 commit: 4ba2788（本体3ファイル）+ 0f08e60（hunterテスト決定論化）、push済み。

## verification_evidence

以下は t_f5f3bc95 の実施中に実行したコマンドと実測出力のみ。

$ python3 scripts/regression_gates_ledger.py | python3 -c "import json,sys; g=json.load(sys.stdin)['gates']['protocol_violation_crash_24h']; print('value=',g['value']); print(g['detail'])"
→ value= 0 / unrecovered rc=0 crashes in last 24h: {} (raw crashed runs=5, recovered-by-restart-or-terminal=5 excluded; …)
（変更前は value=5 't_06fdd792':1,'t_37c0fafa':2,'t_8fabc7c0':1,'t_c6b4e3ed':1 を実測、恒久赤の確認済み）

$ python3 -m pytest tests/test_crash_recovery_gate_v167.py tests/test_regression_gates.py -q -p no:cacheprovider --no-cov
→ 14 passed in 3.16s（新規ユニットテスト4件=未回収1件検出/再run回収/done終端回収/窓外除外、既存ゲート10件維持）

$ python3 -m pytest tests/test_non_api_revenue_hunter_gate.py -q -p no:cacheprovider --no-cov
→ 37 passed in 4.04s（test_cap_three_creates 決定論化で緑。修正前は 'assert 10 <= 3' で失敗を実測）

$ python3 -m pytest -q -p no:cacheprovider --no-cov
→ 1 failed, 652 passed, 5 skipped in 123.96s — 唯一の赤は test_gate_checkpoint_on_exhaustion（t_8fabc7c0 が
   timed_out かつ[checkpoint]0件=別カードの実再発を正しく検知中。t_c6b4e3ed教訓どおり不干渉・24h窓rollで解消見込み）

$ python3 -m mypy scripts/regression_gates_ledger.py --strict
→ Success: no issues found in 1 source file

$ git push（cmd.exe経由）
→ To https://github.com/atushi1841/kensho.git 6305cfb..0f08e60 main -> main

## 受け入れ条件との対応

- 成功指標「pytest test_regression_gates.py が新規crash発生なしで緑」→ 上記14 passedで充足
  （detailは raw=5・recovered=5・unrecovered={} を表示、検知能は未回収経路で維持）
- 実装案1（ゲート自己修復条件の明文化）を採択。案2（conftestマーカーskip）は検知能力を落とすため不採用。
- 応募ロジック・垢情報・モデル切替には未接触（台帳読み取り専用ロジックとテストのみ）。

## Reflexion

{"self_review":{"what_was_done":"protocol_violation_crash_24hゲートに回収判定を追加し未回収crashのみ計上。純関数分離+合成DBユニットテスト4件。hunterテストのボード状態依存も併せて決定論化。","what_went_well":["恒久赤5件→0をその場実測、検知能（未回収=即赤）はユニットテストで保全","evaluate_crash_recovery純関数分離で台帳のDB状態に依存しない再現テストが可能"],"what_could_improve":["共有repoで他ワーカーのgit操作と干渉し編集が一度巻き戻った→コミット前に再grepで自己編集の生存確認を挟む習慣化","test_cap_three_createsの不安定化はt_37c0fafa導入時に気づけた（QA教訓『新規スクリプト名に釣られず既存実装を探す』と同根のテスト衛生盲点）"],"mistakes_or_risks":["回収判定によりdone済み案件のcrash履歴が窓内でも緑になる—crash頻度そのものの監視はdetailのraw計数で継続可能なため許容範囲","pre-commitのruff E501で既存行が再整形された（無関係な1行コメント移動のみ・意図変更なし）"],"learned":"検知専用ゲートは『再発＝未回収』で定義しないと終端済み事故の残骸で恒久赤になり、他ワーカーのpytest -xループを殺す（t_f5f3bc95の本質）。valueとdetail(raw/recovered)を分離すれば検知能を落とさず解消できる。","confidence":9,"verification_evidence":"本ファイル$引用5件すべてt_f5f3bc95実施中の実測出力。"}}
