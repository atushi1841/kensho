# t_23bc6a5c verification — AIチーム成果物受け渡しJSON化（game of telephone回避）

## verification_evidence

- 変更実体: 共有 done-guard に共通生成API `--write-evidence` を追加。
  `write_evidence()` は生成側と検証側が同一モジュール定数
  `EV_JSON_REQUIRED_FIELDS` / `EV_JSON_CONTENT_FIELDS` を共有するため、
  クリティカル→ワーカー→QA の多段受け渡しで形式ドリフト・引用ミスが
  構造的に不可能になる（JSONを手書きしない）。

- 検証対象: `~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py`
  （スキルの doneガード 条件(j) 節も追記）。

$ com1 guard selftest (j_write round-trip) => (
  $ cd ~/.hermes/profiles/kensho-sweeps
  $ bash scripts/kanban_done_guard.py --selftest
  => [t_j_write] normal write pass / empty required list rejected /
     missing artifact rejected / non-object payload rejected
  => ... j_write=True ... (生成→検証 round-trip 成功)
)

$ com2 write-evidence CLI dogfood (positive case) => (
  $ bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py \
       t_clidemo --workdir <tmp>/work --write-evidence --payload-file <payload.json>
  => written: <tmp>/work/reports/t_clidemo_evidence.json
     (guard j verification => pass, sha256=33b925084b...)
  => JSON: success_indicators / verification_commands / artifact_paths /
     evidence_hashes + auto-filled task_id=t_clidemo status=complete
)

$ com3 write-evidence CLI negative case (artifact missing) => (
  $ bash ... --write-evidence --payload-file <payload with /no/such/art.log>
  => error: artifact_paths not on disk (guard j would fail): ['/no/such/art.log']
  => exit 1 （guard が pass し得ない入力を生成前に拒否）
)

$ com4 sweeps repo commit (guard change) => (
  $ cd ~/.hermes/profiles/kensho-sweeps && git add scripts/kanban_done_guard.py
  $ git commit -m "feat(guard): common --write-evidence interface ..."
  => [master 1390165] 1 file changed, 156 insertions(+), 3 deletions(-)
  (local-only repo・push対象外)
)

$ com5 diff scope check (j only, no condition-i/evaluate touch) => (
  $ git diff HEAD -- scripts/kanban_done_guard.py
  => +def write_evidence(...) / +def _selftest_j_write(...) / +if args.write_evidence
  => evaluate()・condition (i)・cron_config_drift_state には触れていない
)

- guard条件(j) 最終確認: reports/t_23bc6a5c_evidence.json を --write-evidence で生成し、
  同モジュールの検証側（evidence_json_state）が pass と自己確認済み。
