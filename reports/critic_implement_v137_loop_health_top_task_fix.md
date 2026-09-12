# critic v137: loop_health top_task 不倒 bug 修正 — 実装・検証記録 (t_296c3dbc)

- Commit: 5bc1a58 fix(loop_health): v137 top_task不倒修正
- 修正: scripts/loop_health.sh line 226/248 `by_age[-1]`(最新規) → `by_age[0]`(最古running)。
  by_age は started_at 昇順(line 160)。2件以上running時に park/escalation target が
  最新規になり SLA parking(24h超滞留判定)が空振りする不倒バグを解消。ヘッダ v137 化。
- テスト: tests/test_loop_health.py 新規3件（不変条件「top_task=最古running」固定）。
- プロファイル実体 ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh へ同期（md5一致）。

## verification_evidence

```
$ cd /mnt/d/Project2/kensho && bash scripts/loop_health.sh --tasks '[{"id":"t_oldest01","status":"running","started_at":1789156822},{"id":"t_newest01","status":"running","started_at":1789189222}]' --state /tmp/lh_test_state_v137.json --dry-run --no-park | jq -r '"top_task=\(.top_task) target=\(.escalation_target) lines=\(.lines[1])"'
top_task=t_oldest01 target=t_oldest01 lines=top=t_oldest01 age=10h
```

```
$ cd /mnt/d/Project2/kensho && git show HEAD:scripts/loop_health.sh > /tmp/loop_health_v136.sh && bash /tmp/loop_health_v136.sh --tasks '...(同上fixture 10h前/1h前)...' --dry-run --no-park | jq -r '"OLD top_task=\(.top_task)"'
OLD top_task=t_newest01
```
（修正前=旧版が最新規を拾う＝bug再現、修正後=最古＝期待動作）

```
$ cd /mnt/d/Project2/kensho && timeout 240 python3 -m pytest tests/test_loop_health.py -v -p no:cacheprovider --no-cov
tests/test_loop_health.py::test_top_task_is_oldest_running PASSED       [ 33%]
tests/test_loop_health.py::test_top_task_single_running PASSED          [ 66%]
tests/test_loop_health.py::test_no_running_top_task_none PASSED         [100%]
============================== 3 passed in 22.20s ==============================
```

```
$ cd /mnt/d/Project2/kensho && bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh --dry-run --no-park | jq -r '"top_task=\(.top_task) running=\(.running) target=\(.escalation_target)"'
top_task=t_296c3dbc running=3 target=t_296c3dbc
```
（任务本文の検証コマンド準拠：running3件のライブボードで最古started=t_296c3dbc(1789190633)と一致。修正前なら最新規t_1bd9b4dd。QA 17:2x中間検証でも同結果確認済）

```
$ md5sum /mnt/d/Project2/kensho/scripts/loop_health.sh /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
ce2f427982cbd573605fa7d9655a33c4  /mnt/d/Project2/kensho/scripts/loop_health.sh
ce2f427982cbd573605fa7d9655a33c4  /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
```
