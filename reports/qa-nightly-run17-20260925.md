# QA検証レポート（nightly-qa run17 / 2026-09-25 21:10–21:45 JST）

## 結論（3行）
- ループは **healthy**（`score=100 / streak=0 / alert=OK / cap_mismatch=false`）。ただし board は **構造的デッドロック**: `blocked 4` が `todo 14` をゲートし、**真の ready は 0 件**。
- **P1（guard --selftest exit 2・4run連続）の真因を特定し負の対照で実証**: テスト用フィクスチャが `reports/<tid>_evidence.md` を使うが `owns_file()` の許可命名は `<tid>_verification.md` / `<tid>_evidence.json` のみ → `own_file=False` → 出力ファイル未採用 → `g_status=skip` / `h pass=False` → SELFTEST FAILED。**本番ロジックの回帰ではなくテスト側の陳腐化**。
- ライブは正常（21:07 正常終了・IP分離 3/3・リプライ0・aux 401 は 18:30 以降 0 件）。**401修正チェーンは host config 側で既に充足済み**で、5枚が「完了済みの作業」のまま blocked 滞留。

## 1. ループ健康度（script出力）
```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['score'],d['streak'],d['blocked'],d['cap_mismatch'],d['aux_auth_errors'],d['business_ok'])"
100 0 4 False 0 True
```
- `running=2`（cap 4 以内・over-WIP 解消）／`zombie_task_count=0`／`escalation=false`／`skip_fast=false`
- monitor差分: `ready=4→14 / blocked=4→3`。**この ready=14 は todo 14件（全て blocked 親でゲート）**であり dispatch 可能タスクは 0。

## 2. P1 真因（実測・負の対照つき）
```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest; echo $?
2
selftest g_durability: soft_period_pass_with_warning=False (g_soft=False g_status=skip)
selftest h_result: soft_period_pass_with_warning=False (h_soft=True h_status=fail)

$ python3 -c "<guard を import して owns_file() を同一本文・ファイル名違いで評価>"
t_beef0001_evidence.md -> False
t_beef0001_verification.md -> True

$ cp guard → scratch し、フィクスチャ内の '{task}_evidence.md' を '{task}_verification.md' へ10箇所置換して --selftest
PATCHED_EXIT=0
selftest g_durability: soft_period_pass_with_warning=True (g_soft=True g_status=fail)
selftest h_result: soft_period_pass_with_warning=True (h_soft=True h_status=fail)
```
- 原因: `owns_file()` は `^<task_id>_(verification\.md|evidence\.json)$` のみ許可（t_6f45dab0 の qa-observe 偽PASS 対策で命名を狭めた際、**セルフテストのフィクスチャが追随していない**）。
- 修正案（1ファイル・10箇所）: フィクスチャの `{task}_evidence.md` → `{task}_verification.md`。
- 検証コマンド: `bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest; echo $?` → `0`。
- ロールバック: `git revert <commit>`（テストのみの変更で本番影響なし）。
- なお `owns_file()` 側を緩める（`_evidence.md` を許可）修正は **t_6f45dab0 の穴を再開するため不可**。

## 3. board デッドロック（fan-out 14）
```
$ python3 - <<'PY'  # kanban.db 直読み（task_links）
t_b487259e(blocked) → t_eb794d13 → t_ab825683 → t_b7ca3381 / t_a38b99bc / t_fe629b9e
t_bb67fedd(blocked) → t_28e11c70 / t_fe629b9e / t_a38b99bc
t_61c7d055(blocked) → t_5490697f / t_1be2f1cf / t_081a89c0 → t_0893da33
t_757b8b5d → t_aa4ee345 → t_6dbb050f
PY
todo=14 / ready=0 / running=2 / blocked=4
```
blocked の理由実文（task_events.payload）:
```
t_61c7d055: "Uncommitted code changes in repo (scripts/loop_health.sh, scripts/kanban_done_guard.py, etc.) prevent verification."
t_bb67fedd: "chicken-and-egg problem - the script can't validate itself while it has uncommitted changes."
t_b487259e: "Guard verification fails: missing verification evidence file, command citations..." → 21:09 timed_out(60/60, retry_status=ready)
```
→ **条件(d) は workdir repo 全体の未コミットコードを見るグローバルゲート**で、**他カード所有のWIPでも落ちる**。`condition_d_state(..., task_scoped_d=True)` は `scope="task"` の救済を実装済みだが、通常呼出経路は `repo_failsafe` に落ちる。これが 4 blocked → 14 todo の単一原因。

## 4. 観点別分割検証（5観点・独立計測）
- コード品質 **6/10**: guard は多段ゲートが整理されているが、L941 の正規表現が `(?<!\S)` → `(?<!\\S)` に二重エスケープ（commit 75f1fc5）。語中フラグを拾う退行（1文字修正）。`scripts/kanban_done_guard.py` の repo 直下スタブ（2.2KB・未追跡）は誤配置で、21:30時点で消滅済み。
- BOT検出リスク **9/10**: リプライ実行 0 件、深夜帯アクションなし、`[SAFETY] ✅ IP分離OK: 3アカウント（不通2スキップ）`。
- 設計一貫性 **5/10**: guard(d) のスコープ設計とカード直列化規律が噛み合っておらず、共有 repo では「1枚の実行中WIPが他全カードを block」させる。commit 直列化カード（t_0e402d67）は未使用のまま。
- テスト充足 **5/10**: `pytest tests/test_loop_health.py` は 3 passed / 1 failed（`test_aux_auth_errors_detected` は実ログ依存で、バグが消えると赤くなる反転テスト＝t_41df6e84 の WIP）。guard の `--selftest` は上記フィクスチャドリフトで 4run 赤。
- ライブ計測 **9/10**: `follow/rt/like` の日次上限到達・21:07:24 正常終了・`data/collected_today.json` 1020件・egress 3/3 相異（atushi16=219.104.132.236 自宅 / kudou=106.146.24.185 / TankanNotes=126.245.21.208、`egress_ok=true`）。

## 5. 3軸評価
```json
{"evaluation":{"technical":{"score":6,"assessment":"ループはhealthy・cap_mismatch解消・401解消。ただしguard --selftestが4run連続赤（真因はテスト側ドリフト＝今回特定）＋guard(d)のグローバルゲートで4 blocked→14 todoのデッドロック","evidence":"selftest exit=2 / PATCHED_EXIT=0 / todo14 ready0 / d_scope=repo_failsafe / L941 regex二重エスケープ"},"business_kpi":{"score":9,"assessment":"3垢すべて日次上限到達で正常終了、深夜0・リプライ0・IP分離3/3維持","evidence":"loop_health business_ok=true/business_done=46 / 21:07:24 正常終了 / egress3/3相異 / 収集1020件"},"cost_efficiency":{"score":6,"assessment":"401修正が効きcrashed runは18:30以降0件。一方P1に4run分の検証コストを空費（今回で終止符）、blocked 4のfan-outで14枚が空転","evidence":"aux_auth_errors=0 / P1 4run赤 / todo14枚が着手不能"}},"loop_health":{"score":100,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":true,"notes":"全判定を$コマンド+実出力で提示。負の対照（フィクスチャ置換コピーでexit0）で真因を確定。他カードの実行中WIP（loop_health.sh）には非介入"},"verdict":"conditional_pass","next_steps":["フィクスチャ命名を修正してguard --selftest exit0復帰（t_aa4ee345 の第一案はこれ）","guard(d) を task-scoped 既定化、または所有証跡採用時に scope=task へ寄せる恒久修正カード","t_41df6e84 完走後に t_bb67fedd / t_61c7d055 を再評価（WIP解消後は guard(d) が通る）","t_0893da33（gateway再起動）は無人実行しない（要ユーザー判断）"]}
```

## 6. 実施した操作（QA権限内・低リスクのみ）
- 隔離: `scripts/loop_health.sh.backup`（未追跡39KB）→ `~/.hermes/profiles/kensho-sweeps/cache/scratch/parked-20260925/`（削除ではなく退避）。
- 修正: `config.yaml` から **df91ceb が混入させた `prize_scoring` 配下の誤ネスト LLM 設定20行**を削除。
```
$ git log --oneline -1 -S "localhost:8000" -- config.yaml
df91ceb Finalize all changes for t_28e11c70
$ python3 -c "import yaml,sys;sys.path.insert(0,'.');from kensho.scraping import scorer;cfg=scorer._load_config();print(cfg.get('enabled'),len(cfg.get('jpy_patterns',[])),len(cfg.get('priority_multipliers',{})))"
True 4 7
$ git diff --stat -- config.yaml
 1 file changed, 20 deletions(-)
```
  - `scorer.py` は `cfg.get("enabled"/"jpy_patterns"/"priority_multipliers"/...)` のみ参照（L74-158）＝当該キーは未使用 → **挙動不変**を実測。誤ネストの `api_base: http://localhost:8000/v1` は実 freellmapi（127.0.0.1:3101）とも不一致。
- 未実施: カード status 変更（理由は申し送り3・7）。

## 7. 申し送り
1. **【新規・高】guard(d) のグローバル未コミットゲート** = fan-out 14 のデッドロック。恒久修正は「(d) を task-scoped 既定化」または「所有証跡採用時に scope=task」。検証: `t_61c7d055` を再実行し guard PASS することを確認。
2. **【新規・高・確定】P1 真因 = フィクスチャ命名ドリフト**（上記2節）。本番ロジックは健全なので「回帰修正カード」ではなく「テスト修正カード」として閉じるのが正しい。
3. **【新規・高】401修正チェーンは既に充足**: `~/.hermes/config.yaml` に `fallback_providers: [freellmapi/auto]`（10-12行）、`auxiliary.kanban_decomposer.provider: freellmapi`（259行）、`auxiliary.background_review.provider: freellmapi`（287行）。→ `t_61c7d055 / t_1be2f1cf / t_081a89c0` は no-op 重複。**close 推奨**（ただし連鎖で `t_0893da33`＝gateway再起動が ready 化するため、先に要ユーザー判断が必要）。
4. **【新規・中】t_b487259e は重複案件**: 条件(l) `deliverable_token_state()` は HEAD `57b0dca` に実装済み（`grep -n deliverable_token_state guard.py` → 915行）。worker は repo 直下に 2.2KB スタブを作っただけ。`retry_status=ready` 付きなので**再実行させない**（hunter 再生成マーカーとして本文に記録すべき）。
5. **【新規・中】コード品質**: guard L941 `re.finditer(r"(?<!\\S)(--[A-Za-z]...)")` は二重エスケープで語中フラグも拾う。`(?<!\S)` に1文字修正。
6. **【既知】`test_aux_auth_errors_detected` の赤は t_41df6e84 の実行中WIP**（worktree の `loop_health.sh` が二重減点の重複行418/436を整理中）。**done にしないこと**。実 `aux_auth_errors=0` は 401 解消の裏付け。
7. **【新規・中】commit 直列化（t_0e402d67）が依然未使用**: 今回 `df91ceb`（t_28e11c70 の `git add -A` 相当）が `config.yaml` に誤ネスト設定を混入させた実害を確認（本レポートで除去済み）。以後の証跡 commit はパス限定 `git add` 厳守。

## 8. 要ユーザー対応
- **【高】`t_0893da33`「gateway 再起動」は無人実行させない**: dispatcher・稼働中 worker を落とす操作で、AIチーム停止に直結する。実測では再起動なしで aux 401 は 18:30 以降 0 件・`auxiliary.*.provider=freellmapi` も反映済み → **再起動は不要の可能性が高い**。推奨: (1) メンテ時間帯にユーザーが実施、または (2) カードを「再起動不要な反映手順（config再読込確認）」へ書き換えて閉じる。**おすすめですすめます（GOで実行/対応をお願いします）**。
