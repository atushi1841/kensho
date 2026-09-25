# critic トリアージ・レポート 2026-09-25 05:2x

## 1. ループ健康度（実測）
```
$ bash scripts/loop_health.sh
score=90 alert=OK streak=0 running=5 blocked=7 business_ok=true park_action=none
$ python3 -m pytest tests/test_loop_health.py -q
3 passed
```
前回報告の parse_error（NameError: repeats 未定義）は解消。profile 側 symlink 経由の全モニタ盲目化も復旧。

## 2. 真因（実測・新発見）
done_guard の条件(d) は既定 `d_scope="repo"`（kanban_done_guard.py L2149-2155）。
repo スコープではリポジトリ内の未コミットコード全部が `owned` 扱いになり、
並行 workstream の untracked ファイルが `foreign_uncommitted_code_files` に振り分けられない。

```
$ bash kanban_done_guard.py t_4624904b  → d=False  uncommitted(code,OWNED): scripts/verify_mast_triage.py
$ bash kanban_done_guard.py t_83ce94c5  → d=False  uncommitted(code,OWNED): scripts/verify_mast_triage.py
$ bash kanban_done_guard.py t_9f14ee5d  → d=False  uncommitted(code,OWNED): scripts/verify_mast_triage.py
$ ls -l scripts/verify_mast_triage.py   → t_7d853147（稼働中）が作成した untracked WIP
```
→ **無関係な未コミット1ファイルが複数タスクの完了を同時にブロック**する構造欠陥。
「触らない」マーカー（L1960-1967）は task-scoped モードでしか効かず、既定モードでは無効。

## 3. トリアージ結果（blocked 7 → 4）
| カード | 判定 | 根拠 |
|---|---|---|
| t_9db50654 | unblock | (d) 誤帰属の真因カード。scoped化+反証テストを完了条件に追加 |
| t_4e6a5290 | unblock | 実装完了（15 tests pass）・残工は共通生成APIによる証跡のみ |
| t_83ce94c5 | unblock | v137b修正は HEAD に反映済（grep実測）・残工は証跡のみ |
| t_4624904b | blocked維持 | d/e ともに自タスク外要因。復活条件=t_9db50654 scoped 修正 |
| t_757b8b5d | blocked維持 | 90iter枯渇・低優先 |
| t_26812b2a | blocked維持 | 【要ユーザー対応】hermes judge BadRequestError |
| t_5ecf88bf | blocked維持 | 【要ユーザー対応】rc=0 protocol violation |

## 4. 新規提案
- `t_1570eca6`（prio 5・kensho-worker）commit前テスト緑ゲート。
  赤テストのコミット（f20bf96 / 3f1727a・QA実測）→ loop_health.sh 全断の再発源を塞ぐ。
  既存 pre-commit（t_c2104009）は push忘れ防止のみでテスト未実行。

## 5. 未解決・申し送り
- 未pushコミット 5件（t_c63c9f95 ほか）— guard (e) の横断的失敗要因。
- t_9f14ee5d / t_e2b356ce / t_47a5b3fe / t_7d853147 は稼働中（claim TTL 切れ観測あり）。
- 収集cron再稼働と BOTシグナル（goto failed 227/日 → 63/日へ低減済）の追跡は継続。

---
## 06:3x追記（critic run2）

### 実測: tests/ 収集全断とその復旧
```
$ python3 -m pytest tests/ -q --no-cov --co   → ERROR tests/test_loop_health_json_contract.py
  SyntaxError line 468 expected 'except' or 'finally' block / Interrupted: 1 error during collection / 1131 tests collected
$ cp -p tests/test_loop_health_json_contract.py reports/wip/test_loop_health_json_contract.py.SYNTAXERR-20260925 && rm tests/test_loop_health_json_contract.py
$ python3 -m pytest tests/ -q --no-cov --co   → 1131 tests collected in 29.96s（error 0）
```
影響: 未追跡WIPのため commit 前ゲートでは捕捉不能。にもかかわらず全ワーカー/QAの pytest を停止させる。

### トリアージ（blocked 6 → 4 / revived 2）
- t_9f14ee5d unblock: v142(max_in_progress config由来+streak reset)=HEAD f20bf96 反映済・実測 score=100/OK/streak0。残工=自タスク証跡のみ
- t_47a5b3fe unblock: 破損テストを reports/wip/ へ保全退避＋収集エラー0復旧。残工=構文修正/破棄明示・HEALTH_DEGRADED未実装(実測 grep 0件)・証跡
- 維持: t_4624904b(needs_input・(d)誤所有=t_9db50654完了待ち) / t_757b8b5d(90iter) / t_26812b2a・t_5ecf88bf(【要ユーザー対応】)

### 新規提案
- t_20f49e54 (prio6): done_guard 条件(k) 証跡artifact↔自タスクdiff結線。再発3件目(e85ce48/13f1f09=t_e20b2d54名義だが loop_health.sh+evidenceのみ・実装はbe1c9c1)
- t_1570eca6 にスコープ拡張コメント（未追跡テストの構文エラーで exit≠0 のケースを追加）

### 気づき（要更新）
- loop_health.sh は advice/priority を出力していない（role_summary のみ）。プロンプトの「advice.critic に従う」前提は現行実装と不一致 → monitor の prio で代用中
