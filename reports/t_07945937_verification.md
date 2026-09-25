# t_07945937 検証レポート — doneガード条件(bind): 証跡 artifact_paths × 自タスクdiff の結線

タスク t_07945937（担当 kensho-worker / 実行 kensho-revenue-worker）の実装・検証記録。
blocked 理由「実装作業の痕跡(git_dirty)があるのに kanban_complete/block が未呼び出し」からの復活run。

## 結論

done ガードの条件(j) は「evidence.json の必須フィールド非空」＋「artifact_paths が実在」しか見ないため、

```
タスク名で任意のファイルをコミット + 実在パスを並べた evidence.json
```

だけで通過できた（t_47a5b3fe / t_20f49e54 の共通根 = 実装成果物が HEAD に無い偽done）。
今回この経路を塞ぐ**条件(bind)**を追加し、t_07945937 の偽done再現ケースで **検出 0/1 → 1/1** を実測した。

- 実装: `scripts/done_guard_evidence_binding.py`（repo側チェッカー・CLI付き）
- 結線: `~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py`（profile側 done ガードに条件(bind)を追加）
- テスト: `tests/test_done_guard_evidence_binding.py`（11件）
- 再現ハーネス: `scripts/repro_done_guard_fake_route.py`（一時repoで完結・共有repo非破壊）

移行期間は soft（`BIND_HARD_AFTER = 2026-10-01`、それ以前は WARNING のみで pass 判定は不変）。
`KANBAN_GUARD_BIND_HARD=1` で即 hard（exit 1）に切り替えられる（段階導入・回帰テスト用）。

## verification_evidence

### 1. チェッカー自己検証（一時repoで pass/fail/skip/幽霊commit）

$ python3 scripts/done_guard_evidence_binding.py --selftest
[selftest] pass: want=pass got=pass
[selftest] fail: want=fail got=fail
[selftest] skip: want=skip got=skip
[selftest] ghost source_commit: want=fail got=fail
[selftest] ALL OK

### 2. 単体テスト（t_07945937 の新規テスト11件）

$ timeout 900 python3 -m pytest tests/test_done_guard_evidence_binding.py -q --no-cov
collected 11 items
tests/test_done_guard_evidence_binding.py ...........                    [100%]
11 passed in 7.49s

### 3. 偽done経路の再現（before / after soft / after hard）

偽done再現 = 「成果物は過去commitに実在するが、タスク名の commit はコード成果物に触れていない」状態。
旧ガード（`.bak-20260925`）はこの状態を **exit 0 / pass=True** で通していた。

$ timeout 900 python3 scripts/repro_done_guard_fake_route.py /home/atushi/.hermes/profiles/kensho-sweeps/cache/scratch/fake_done_repro_final
--- before_soft: exit=0 pass=True bind=ABSENT j=True failing=[]
--- after_soft: exit=0 pass=True bind=True j=True failing=[]
--- after_hard: exit=1 pass=False bind=False j=True failing=['bind:artifact_paths_bound_to_task_diff']

- before（旧ガード）: **exit=0 / pass=True**（= 偽doneが通る）
- after soft（新ガード・既定）: exit=0 だが `bind_status=fail` を検出し WARNING 出力（移行期間の設計どおり）
- after hard（`KANBAN_GUARD_BIND_HARD=1`、10/01以降と同条件）: **exit=1 / failing=[bind]**（偽done閉鎖）
- bind の note: `code_artifacts=1 bound=0 unbound=scripts/fake_impl.py | no declared code artifact bound to this task's commits/diff`

### 4. 正規ケースの回帰（誤BLOCKしない）

$ python3 scripts/done_guard_evidence_binding.py --validate <一時repo>/reports/t_facade02_evidence.json --task-id t_facade02 --workdir <一時repo>
bind: pass — code_artifacts=1 bound=1 | code artifact bound to task commits/diff

期待通り pass（exit 0）。成果物をタスクID入りメッセージで commit した通常カードは止まらない。

### 5. 既存条件への回帰（additive の実測）

$ python3 kanban_done_guard.py.bak-20260925 t_572b88de --workdir /mnt/d/Project2/kensho --json  （旧）
$ python3 kanban_done_guard.py            t_572b88de --workdir /mnt/d/Project2/kensho --json  （新）
（比較結果）
before pass= False after pass= False
before conds= 11 after conds= 12
added keys: {'bind:artifact_paths_bound_to_task_diff'}
changed existing conds: []

→ 既存11条件は1つも変化せず、新条件のみ追加（additive）。既存カードの判定は不変。

### 6. 型検査・関連テスト・push

$ timeout 600 python3 -m mypy scripts/done_guard_evidence_binding.py tests/test_done_guard_evidence_binding.py
Success: no issues found in 2 source files

$ timeout 600 python3 -m pytest tests/test_outcome_review_check.py -q --no-cov
14 passed in 1.45s

$ git push origin main
To https://github.com/atushi1841/kensho.git
   274e9e7..ad08fd0  main -> main

$ git rev-list --left-right --count origin/main...main
0	0

## Outcome Review（数値）

- 指標: 偽done再現ケース（artifact_paths が自タスクdiffに無い evidence.json）のガード検出件数
- before = 0/1（旧ガードは exit 0 で通過）→ after = 1/1（hardモードで exit 1）
- 副次指標: 条件数 11 → 12（既存条件の変化 0 件）/ 新規テスト 0 → 11 passed

## 変更ファイル

- `scripts/done_guard_evidence_binding.py`（新規・チェッカー本体）
- `tests/test_done_guard_evidence_binding.py`（新規・11テスト）
- `scripts/repro_done_guard_fake_route.py`（新規・再現ハーネス）
- `~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py`（条件(bind)結線・`.bak-20260925` 退避済）
- 回収: blocked attempt が残した `kensho/kanban_done_guard.py` を commit 3e7c523 で保存したうえで
  本実装へ fold（削除）

## 留意（申し送り）

- プロトタイプのテスト（dangling ea78e29 収録）は cleanup に `git reset --hard` を使っており、
  共有repoでは兄弟タスクの成果を消し得るためそのままは採用していない。同じ検証は tmp_path の
  一時repoで完結する形へ置き換えた（9/25 に3カード消失が実際に起きている）。
- `tests/test_regression_gates.py` に既存FAIL 4件（empty-result done 6/72、unrecovered rc=0 crash 2件、
  checkpoint 未打刻 2件、notepad lessons 8 bullets > 5）。いずれも kanban DB / notepad 側の別件で、
  本変更（ガード条件の追加）とは無関係。
- 未コミットの作業ツリーには他ワーカー（実行中4件）の成果が残っている。共有repoのため触っていない。

## done guard（実測コピー）

$ timeout 600 python3 ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_07945937 --workdir /mnt/d/Project2/kensho
kanban_done_guard task=t_07945937 -> PASS (all conditions satisfied)
  worker_output_file : /mnt/d/Project2/kensho/reports/t_07945937_verification.md
  own_file            : True  (owner_task_id=t_07945937)
  a verification_evidence : True
  b command cites >=3     : True  (count=9)
  c no false-done marker  : True
  d no uncommitted code   : True  (scope=task)
  e pushed + hash ancestry: True  (ok)  0 unpushed commits | hashes: 1 hash(es) cited, 0 invalid
  f no dep drift (pyproject vs venv)     : True  (skip drift=0)  cached (758s ago): No broken requirements found.
  g evidence durable (git   tracked)   : True  (pass)  evidence tracked: reports/t_07945937_verification.md (durability: in-repo)
  h result nonempty (--result at complete)  : True  (skip)  completion payload unknown — result check deferred to post-done audit
  j evidence.json machine-readable : True  (pass)  /mnt/d/Project2/kensho/reports/t_07945937_evidence.json  machine-readable evidence.json valid (fields 0 missing)
  k outcome review   (before/after) : True  (pass)  before/after comparable metric present
  bind artifacts×task diff (t_07945937) : True  (pass)  code_artifacts=4 bound=3 unbound=/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py | code artifact bound to task commits/diff

$ KANBAN_GUARD_BIND_HARD=1 timeout 600 python3 ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_07945937 --workdir /mnt/d/Project2/kensho
kanban_done_guard task=t_07945937 -> PASS (all conditions satisfied)
  bind artifacts×task diff (t_07945937) : True  (pass)  code_artifacts=4 bound=3 unbound=/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py | code artifact bound to task commits/diff

→ hard（`KANBAN_GUARD_BIND_HARD=1` = 10/01以降と同条件）でも正規カードは PASS（誤BLOCKゼロ）。
  unbound の1件は profile 側 `kanban_done_guard.py`（repo外＝diffに現れない）で、最低1件の結線要件は
  他3件の repo 内コード成果物で満たしている。
