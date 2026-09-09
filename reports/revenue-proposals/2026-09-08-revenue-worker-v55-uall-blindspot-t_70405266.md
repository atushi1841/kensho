# revenue-worker v55 — git untracked-dir ブラインドスポット修正 (t_70405266)

日付: 2026-09-08 12:45〜13:0x JST（cron 5e8ec4984bba / monitor起動）
対象タスク: t_70405266（worker自前提案、idempotency-key=worker-20260908-v55-uall-fix）
優先度: 高（自動判定②自動復旧を阻害 — v54 dirtyフラグの残存ギャップ）

## 起動契機
monitor差分: `score=75|...|wip=4` → `score=95|ready=0|blocked=0|wip=0|done=317|prio=new_proposals`
（v52〜v54で blocked/wip が全クリーン、done 312→317）。ready=0 供給不足 = new_proposals。

## 問題（実測エビデンス）
`kanban_done_guard.py::git_uncommitted_code_files()` と `board_state_monitor.sh` の dirty判定は
どちらも `git status --porcelain`（既定 = `-u=normal`）。git は新規ディレクトリ内の未追跡ファイルを
親ディレクトリ1行に畳む（`?? scripts/_blindspot_test/`）ため、**新ディレクトリ配下の未コミット .py** が
guard cond(d) と monitor dirty=Y の両方に同時に見えない。

v54（t_76fe92e5）で dirty フラグを入れた直後に、その判定自体が同じ盲点を持つことを発見。
特に v52 教訓「使い捨て解析スクリプトは作成時に git add」の実践形（新dirにスクリプトを置く）で
連鎖ブロックが再発しうる。

## 実装内容（2ファイル・各1行）
1. `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py`
   - `status --porcelain` → `status --porcelain -uall`（timeout 20→30、WSL/mnt/d実測2.1秒のため）
   - docstringに理由と実測記録を追記
2. `/home/atushi/.hermes/scripts/board_state_monitor.sh`
   - 同 `-uall` 追加（guard と同一規則へ統一のコメント付き）

プロジェクトリポジトリ（/mnt/d/Project2/kensho）のコードファイルは一切変更なし。
フック `kanban_done_guard_hook.sh` は guard を呼ぶだけなので自動で新挙動に追随。

## verification_evidence

すべて実測（2026-09-08 12:5x〜13:0x JST）。

```
$ python3 -m py_compile .../kanban_done_guard.py
COMPILE_OK
$ bash -n /home/atushi/.hermes/scripts/board_state_monitor.sh
BASH_SYNTAX_OK

# A. 現ツリーでの誤爆チェック（-uall化後も未コミットコード=0）
$ python3 -c "... guard.git_uncommitted_code_files('/mnt/d/Project2/kensho')"
guard sees: []

# B. ブラインドスポット再現（新dir配下 .py）→ 修正後に検出されること
$ mkdir -p scripts/_blindspot_test && printf 'x=1\n' > scripts/_blindspot_test/probe.py
$ python3 -c "... guard.git_uncommitted_code_files(...)"
guard sees: ['scripts/_blindspot_test/probe.py']     # ← 修正前は [] だった（v54実測で確認済み）
$ bash /home/atushi/.hermes/scripts/board_state_monitor.sh | grep -o 'dirty=[YN]'
dirty=Y                                              # ← 修正前は dirty=N で素通り

# C. クリーン後への復帰 + monitor冪等性（同一状態2連続で署名完全一致）
$ rm -rf scripts/_blindspot_test
$ bash board_state_monitor.sh; bash board_state_monitor.sh; diff → IDEMPOTENT_OK
score=95|ready=0|blocked=0|wip=1|done=317|prio=new_proposals|streak=0|esc=False|skip=False|dirty=N

# D. guard 本体のスモーク（既存doneタスクで条件dが正しくTrue）
$ python3 kanban_done_guard.py t_4e678707 --soft
  d no uncommitted code   : True
```

成功指標3項目すべて合格: ①probe→guard/dirty両方Y遷移 ②クリーン後2連続署名一致 ③現ツリー誤爆0。

## 自己レビュー（Agent Self-Review Loop）
- 変更差分 = `-uall` とコメントのみ。意図しない変更なし（diff確認済）
- 署名の安定性: dirtyは真偽値のみ維持（件数・ageは含めない=v54制約遵守）
- 性能: git status -uall 実測2.1秒（monitor tick毎の許容内）
- セキュリティ: キー・認証情報なし。done判定は厳格化方向のみ（既存doneに影響なし）
- プロジェクトリポジトリのコードツリーはクリーン維持（NO_REPO_CODE_DIRTY実測）

## 申し送り
- critic: v54提案（dirtyフラグ）と本v55修正は同一系統（done_guard可視性）。これで鎖は閉じたはず。
  次の監視点は「guardの他条件（a/b/c）にも同種の盲点がないか」の一度きりの棚卸し。
- reddit t_bef61602 は scheduled（9/28+、ユーザーPhase1待ち）で減点対象外。cf判定cron 9/11 10:00、
  stealth-check検証 9/14 は予定通り他レーンで自動発火。

```json
{"self_review":{"what_was_done":"t_70405266: kanban_done_guard.py と board_state_monitor.sh の git status を -uall 化し、新規ディレクトリ配下の未コミットコードに対する cond(d)/dirty フラグのブラインドスポットを修正（2ファイル各1行+コメント）","what_well":["v54のdirtyフラグ直後に残存ギャップをprobe実測で先回り特定","guard/monitorの判定規則を同一(-uall)に統一し乖離を恒久防止","プロジェクトリポジトリを一切汚さずdone_guard条件dを維持"],"what_could_improve":["probe検証は新dirパターンだけでなく rename+untracked 混在ケースも次回棚卸しで確認したい"],"mistakes_or_risks":["-uallで未追跡ファイル一覧が長くなる（大規模untracked時にgit遅延リスク、timeout 30sで緩和）"],"learned":"git porcelain の既定 -u=normal は dir 畳みする。『未コミット検出』をやるツールは必ず -uall を使う。v54で入れた検出機構自体に同じ盲点があったのは、機構を『入れた』で止めず『入れた後にprobeで逆テスト』して初めて見つかった","confidence":9,"verification_evidence":"py_compile OK / bash -n OK / 現ツリー guard sees=[] / probe.py で guard sees=['scripts/_blindspot_test/probe.py'] + dirty=Y / rm後 dirty=N + 2連続署名一致(IDEMPOTENT_OK) / guard --soft t_4e678707 条件d=True"}}
```
