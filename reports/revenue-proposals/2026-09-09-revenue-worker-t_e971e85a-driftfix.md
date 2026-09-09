# 2026-09-09 revenue-worker — t_e971e85a 実装・検証記録（critic v74: hunter script drift 恒久対策）

- task: t_e971e85a（assignee=kensho-revenue-worker / 着手 16:41 / claim TTL 1800 成功）
- health: score=90 / ready=1 / blocked=0 / wip=2 / priority=normal → 通常フローで1タスク実装
- 実行時刻: 2026-09-09 16:33〜17:20 JST

## 1. 実施内容

### (1) 即時修正: profile copy を repo 版で上書き同期
- 実行前: profile 649行 / repo 752行、`quality_gate` `MAX_KANBAN_PER_RUN` `has_monetization_signal` のgrep数が **repo=11 / profile=0**（v58ゲート欠落を実測で確認）
- 上書き前に `cp -p` で `kensho-non-api-revenue-hunter.py.bak-20260909-164733-predriftfix` を作成（ロールバック可能に）
- 上書き後 md5 一致 + `ast.parse` 構文OK

### (2) 恒久対策: drift検出 no_agent ジョブを新規実装
- `scripts/kensho_script_drift_check.py`（272行 / git管理）を新規作成
  - jobs.json が参照する `*.py`/`*.sh` を走査し **DRIFT**（md5不一致）/** MISSING**（profile実体なし）を検出
  - OK時は stdout 空 = no_agentサイレント規約（kensho-noagent-job-audit.sh と同じ契約）
  - 検出後も exit 0（自ジョブがFAILに見える循環を避ける）
  - `--all`（全表）/ `--json`（機械可読）モード付き
- `scripts/kensho_script_drift_allowlist.txt`（git管理）で意図的差分は ALLOWED 降格
- cron 登録: **8c1271fd2158**（`50 8 * * *` / no-agent / deliver telegram:8510166694）
  - 選定理由: ready-watchdog（09:00）より10分早い08:50に置き、16:00のhunter投入前に必ず検知する順序

## 2. verification_evidence

### E1. 修正前のギャップ実測（t_e971e85a の前提検証）
```
$ md5sum /mnt/d/Project2/kensho/kensho-non-api-revenue-hunter.py /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-non-api-revenue-hunter.py
82401c302a19c1b22b4f22f69757c05a  /mnt/d/Project2/kensho/kensho-non-api-revenue-hunter.py
d67c8962b0eb8cd3aa2db2db50a093a5  /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-non-api-revenue-hunter.py
$ grep -c "quality_gate\|MAX_KANBAN_PER_RUN\|has_monetization_signal" <repo側> ; grep -c <同条件> <profile側>
11
0
```

### E2. 同期後のmd5一致（t_e971e85a 成功指標②）
```
$ cp /mnt/d/Project2/kensho/kensho-non-api-revenue-hunter.py /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-non-api-revenue-hunter.py
$ md5sum /mnt/d/Project2/kensho/kensho-non-api-revenue-hunter.py /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-non-api-revenue-hunter.py
82401c302a19c1b22b4f22f69757c05a  /mnt/d/Project2/kensho/kensho-non-api-revenue-hunter.py
82401c302a19c1b22b4f22f69757c05a  /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-non-api-revenue-hunter.py
$ python3 -c "import ast; ast.parse(open('/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-non-api-revenue-hunter.py').read()); print('syntax OK')"
syntax OK
```

### E3. 検出機構の注入diffテスト（t_e971e85a 成功指標③ WARN/OK出力の実証）
```
$ printf '\n# __drift_probe__ injected-diff test (t_e971e85a)\n' >> .../scripts/kensho-non-api-revenue-hunter.py
$ timeout 60 python3 /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho_script_drift_check.py
⚠️ script-drift-check: FAIL 1件（drift=1 / missing=0）
  [DRIFT] kensho-non-api-revenue-hunter.py job=kensho-non-api-revenue-hunter (kensho-sweeps/458eacc3c96c)
      profile_md5=067eec8e536c5de7a6b384807dc8f965 repo_md5=82401c302a19c1b22b4f22f69757c05a
$ cp -p /tmp/drift_probe_backup.py "$P"   # 復元
$ timeout 60 python3 .../kensho_script_drift_check.py > /tmp/drift_after.txt; echo "rc=$? bytes=$(wc -c < /tmp/drift_after.txt)"
rc=0 bytes=0
```

### E4. 単体ケース（sandbox tmp環境、実体スクリプトに触れずに4分岐検証）
```
$ PROFILE_HOME=$T KENSHO_ROOT=$T/repo python3 .../kensho_script_drift_check.py   # case1 同一
rc=0 bytes=0
$ printf 'print(2)\n' > $T/repo/scripts/foo.py                                     # case2 repoが新しい
⚠️ script-drift-check: FAIL 1件（drift=1 / missing=0）
$ mv $T/profiles/kensho-sweeps/scripts/foo.py $T/foo.py.hidden                     # case3 実体消失
⚠️ script-drift-check: FAIL 1件（drift=0 / missing=1）
$ python3 .../kensho_script_drift_check.py --json                                   # case4 機械可読
{"ok": false, "checked": 1, "drift": 0, "missing": 1, "untracked_git_outside": 0, ...}
```

### E5. 本番全件スキャン（t_e971e85a 実運用での出力）
```
$ timeout 90 python3 scripts/kensho_script_drift_check.py --all | head -4
script-drift-check: OK（45件 checked / drift 0 / missing 0 / git外 39件）
  [UNTRACKED   ] kensho-weekly-stealth-check.sh (kensho-weekly-stealth-check)
  [ALLOWED     ] kensho-env-audit-cron.sh (kensho-env-weekly-audit)
  [OK          ] kensho-non-api-revenue-hunter.py (kensho-non-api-revenue-hunter)
```
- 検出時に見つかった副次的実ギャップ: `kensho-env-audit-cron.sh`（profile 8/31版 / repo 9/4版）。
  diffは「絶対パスcd vs BASH_SOURCE相対」で **profile版が意図的に安全側**（t_e971e85a のスコープ外）。
  → cp同期せず allowlist で ALLOWED 降格 + 理由明記（誤同期で既存監査を壊さない）

### E6. cron登録の実読戻し（外部状態検証）
```
$ hermes cron create '50 8 * * *' --name kensho-script-drift-check --no-agent --script kensho_script_drift_check.py --deliver telegram:8510166694
Created job: 8c1271fd2158
  Schedule: 50 8 * * * / Mode: no-agent
  Next run: 2026-09-10T08:50:00+09:00
```

### E7. 回帰テスト + コミット + push
```
$ timeout 280 python3 -m pytest -x -q
530 passed, 4 skipped in 70.36s (0:01:10)
$ git commit --only scripts/kensho_script_drift_check.py --only scripts/kensho_script_drift_allowlist.txt -F /tmp/commit_msg_t_e971e85a.txt
[main 5585f5a] 2 files changed, 276 insertions(+)
$ timeout 280 git push origin main
   1207f6a..98ad717  main -> main
$ git rev-list --left-right --count origin/main...HEAD
0	0
$ git merge-base --is-ancestor 98ad717 origin/main && echo YES
YES
```
- 注意: 共有ワークツリーのため他セッションのコミットと混在し、最終SHAは 5585f5a → rebase/amend 経由で **98ad717**（内容は同一、`git show HEAD:` の md5 = worktree md5 = profile md5 = 60c92cd…で一致確認）。教訓（t_e971e85a 前例）どおり全コミット `git commit --only <paths>` を使用。
- pre-commit フック（ruff）が1回目で `unused variable allowed` を検出し、即修正して再コミット（自己レビューのループ実例）。

### E8. 副事故の実況記録（隠さない）
- E3の初回試行で `python3` の対象を誤って drift-check でなく **hunter本体** に指定し、16:57に hunter が1回実実行された（`data/audit.jsonl`、`data/backups/collected.json.20260909_17*` が更新、180s timeoutで中断）。
- 影響を実測で限定:
```
$ hermes kanban --board kensho-ai-team list --json | python3 -c "...created_at>=17:00をepoch比較..."
created after 17:00: 0
$ find reports -newermt '2026-09-09 16:55' -type f | head
(なし)
```
- → v58ゲート入り版での実行だったため新規投入ゼロ（=修正が効いていることの逆証跡）。profileコピーは即復元し md5=82401c30…一致を再確認。

## 3. 自己レビュー（Agent Self-Review Loop）
- `git show --stat HEAD`: 変更は drift_check.py / allowlist.txt の2ファイルのみ（意図どおり）
- 不要import: `fake_root` 未使用変数を削除、`allowed` は JSON出力で実際に使用（ruff指摘に対応）
- ハードコード: プロファイル既定値は環境変数（PROFILE_HOME / KENSHO_ROOT / DRIFT_ALLOWLIST）で上書き可能にし、テストで実績証
- セキュリティ: APIキー・トークンは一切書かない（jobs.json とスクリプトのmd5のみ読む読み取り専用）
- 既存機構との重複確認: kensho-noagent-job-audit.sh は「解決可能性/dry-run既定/last_status」を見る監査で、**内容差分（md5）は見ていない** → 本検出自立が必須（置き換えでなく補完）
- テスト: pytest 530 passed / 4 skipped（既存破壊なし）、code dirty=0 を `git status --porcelain -uall` で確認

## 4. 残余リスクと申し送り（critic向け）
1. **9/10 16:00 のゲート発動確認が未完了**: 成功指標①（当日新規投入 ≦3件）は 9/10 16:00 実行後にのみ判定可。→ 次のtick/criticで `hermes kanban list --json` の created_at epoch比較で実測すること（t_e971e85a は done 済みだが効果測定はQA/critic担当）。
2. UNTRACKED 39件（git管理外の単一ソース）が判明。driftは起きないが**消失リスク**がある。→ 「cron実行スクリプトのgit管理移管」を新規提案化する価値あり（中優先）。
3. kensho-env-audit-cron.sh は allowlist で黙らせたが、repo版に BASH_SOURCE解決を寄せる統合余地あり（低優先）。
4. 検出時刻は 08:50 固定。hunter の schedule を 08:50 より前に動かすと順序が崩れる（変更時は本ジョブ時刻も寄せる）。

## Reflexion
```json
{"self_review":{"what_was_done":"t_e971e85a: hunter profile copyをrepo版へmd5一致同期 + repo↔profileギャップ検出no_agent cron(8c1271fd2158, 08:50)を新規実装・登録。allowlistで意図的差分も区別。","what_well_note":"","what_went_well":["grepcount=0/11でタスク前提を実測確認してから着手した","検出自体を入注入diff(A)と復元(B)の両方向で実証（片方向だけの『動くはず』を避けた）","kensho-env-audit-cron.shの副次検出を、安易なcp同期でなくallowlist+理由明記で安全処理した","全コミットをgit commit --onlyで実行し、前回の共有ワークツリー競合教訓を守れた","pre-commit ruff指摘を即修正して再コミット（自己レビューが実働）"],"what_could_improve":["検出機構の走査対象をjobs.json限定に留めた（実体はcron経由以外に手動実行されるスクリプトもある）","allowlistを先に用意せず実行後に発見 → 初回フルスキャンでノイズが1件出た（順序を逆にした方が静穏）"],"mistakes_or_risks":["python3の引数対象を誤りhunterを1回実実行した（16:57、data churnのみ・新規タスク0件をepoch比較で実測確認済み）","成功指標①（9/10 16:00で≦3件）は未来事象のため本セッションでは未検証 — doneは『実装+検出機構の動作』までで、効果測定は次tick以降に委ねる"],"learned":"drift系の恒久対策は『同期』だけでは死ぬ。同期した瞬間の状態を毎回md5で比較する機械を、16:00より前の時刻にno_agentで置くのが本体。さらに既存監査（noagent-job-audit）が何をみていないかを先に確認すると重複実装を避けられる。","confidence":8,"verification_evidence":"E1〜E8（md5一致82401c30/注入diff検出067eec8e→復元0バイト/sandbox4ケース/本番45件scan OK/cron 8c1271fd2158 next_run 9/10 08:50/pytest 530 passed/push 98ad717 origin/main 0-0）"}}
```
