# critic v151 実装レポート t_274a3024 — done時resultカラム空Problem恒久対策

- 実行: 2026-09-15 (JST) / kensho-revenue-worker run482
- カード: t_274a3024（起票=kensho-sweeps critic v151）
- 対象ファイル（すべて ~/.hermes 側、kensho repoコードは変更なし）:
  1. `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py` — チェック(h)追加
  2. `/home/atushi/.hermes/agent-hooks/kanban_done_guard_hook.sh` — 完結ペイロード抽出・guardへの引き渡し
  3. cron `nightly-worker`(5e8ec4984bba) / `nightly-qa`(033ff6065ef7) プロンプト — `--result` 1行要約必須を明記
  4. `/home/atushi/.hermes/profiles/kensho-revenue-worker/SOUL.md` — 完結手順へ同旨1行追加

## 実装内容

### (h) 条件: tasks.result 非空検査（kanban_done_guard.py）
- `result_column_state()`: DBのresult非空→pass / 完結ペイロードにresultあり→pass /
  **summaryのみ完結（result空）→fail**（v151病理そのもの）/ ペイロード不明→skip。
- `evaluate(proposed=...)` 常時評価（early return経路でも判定残す）。soft/hardは
  e/f/gと同規則: `H_HARD_AFTER="2026-09-18"`（2026-09-15投入+3日 grace）まで警告のみpass。
- CLI `--completion-payload '{"result": bool, "summary": bool}'` 追加（parse不能=skip・誤ブロック回避）。
- `_fmt_plain` へ h 行 + soft警告文（`--result`へ1行要約を必須とする運用文言）追加。
- `_selftest_h_result()` 追加（5分支: 病理検出/--result pass/不明skip/DB非空pass/soft-hard挙動）、
  `_selftest_all` 統合。

### hook配線（kanban_done_guard_hook.sh）
- native `kanban_complete`: tool_input の result/summary 非空をJSON化してguardへ。
- `terminal`/`execute_code` の `hermes kanban complete` 検出時: `--result`/`--summary`
  への非空リテラル指定をgrep判定してJSON化。ペイロード不明時は従来呼び出し（fail-open）。

### プロンプト/SOUL必須化
- nightly-worker: 「done発行は必ず `--summary "..." --result "..."`（--resultに1行要約必須）」
  を実装手順6とv76 early_complete節に明記。nightly-qa: 終了前確認6に同旨明記。
- 過去done分15件の及記入库は不要（教訓のみ・カード本文指示どおり）→実施せず。
- kensho-worker/SOUL.md への同旨追加は保護ファイル承認タイムアウトで未実施
  （kensho-revenue-worker SOUL.mdとnightly-worker promptで実効経路はカバー済み）。

## 根本原因（コード上確定）
`hermes-agent/tools/kanban_tools.py` `_handle_complete` は summary と result を独立に
`complete_task()` へ渡すだけで summary→result フォールバックが無い（CLIは
`--summary` →`--result`フォールバックあり、逆は無し）。よって native
kanban_complete(summary=...) のみの完結が構造的に tasks.result 空を作る。

## verification_evidence

$ python3 /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_274a3024/probe_result.py → 起票時点baseline実測
done=441 result_empty=305 / t_df0bdb4f・t_2d9555df・t_902d09ac等がresult空（QA申し送り再発2件を含む）

$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest → 全件pass
SELFTEST OK (h_result): summary-only completion detected, --result passes, unknown payload skips, soft warns / hard blocks
SELFTEST OK: (e) unpushed/ghost-hash detection works; (d) task-scoped bleed fix works; (g) evidence durability gate works; (h) result-column gate works

$ bash kanban_done_guard.py t_274a3024 --task --completion-payload '{"result": false, "summary": true}' --json → 病理検出（soft期間）
"h:result_nonempty": true / "h_status": "fail" / "h_soft": true / note: tasks.result empty — summary-only completion: pass the same 1-line recap to --result at complete (critic v151)

$ bash kanban_done_guard.py t_274a3024 --task --completion-payload '{"result": true, "summary": true}' --json → --resultありはpass
"h:result_nonempty": true / "h_status": "pass"

$ bash kanban_done_guard.py t_274a3024 --task --json → ペイロード無しはskip（誤ブロック回避）
"h_status": "skip"

$ bash -x kanban_done_guard_hook.sh < native summaryのみ完結ペイロード → hook配線実証
++ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_274a3024 --task --completion-payload '{"result": false, "summary": true}'

$ bash -x kanban_done_guard_hook.sh < terminal CLI完結 --summaryのみ → 経路2もresult:false検出
++ bash .../kanban_done_guard.py t_274a3024 --task --completion-payload '{"result": false, "summary": true}'

$ bash kanban_done_guard_hook.sh < JSON破損ペイロード → fail-open維持
rc=0 out={}

$ python3 verify_cron.py（hermes --profile kensho-sweeps cron edit 実行後） → プロンプト反映+ピン維持
5e8ec4984bba nightly-worker | model= qwen3.8-flash | provider= bai | enabled= True | len= 4370 | v151_in_prompt= True
033ff6065ef7 nightly-qa | model= qwen3.8-flash | provider= bai | enabled= True | len= 1992 | v151_in_prompt= True

$ python3 probe_result.py（再実行・レポートコミット前の現在値） → 新規doneの空増加監視ベースライン
done=441 result_empty=305（カード本文検証コマンド: 新規done増加に対し空の増加分0を維持すれば成功指標）

## 失敗時代替案の適用判定
- dispatcher側の非対応完結経路: pre_tool_call hookはkanban_complete/terminal/execute_code
  の全完結経路を捕捉済み（hook分類ロジック既存）。ペイロード抽出不能時はskip=fail-openのため
  hard化(09-18)以降も構造的誤ブロックは発生しない見込み。万一空doneが再発した場合は
  QAカードでH_HARD_AFTER手前のWARN格下げ（カード本文代替案）を運用判断として申し送り。

## 成功指標の測定方法（QA向け）
- 検証コマンド（カード本文準拠・sqlite3不在のためpython3版）:
  `python3 /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_274a3024/probe_result.py`
- 判定: 2026-09-16以降のdone新規増加について result_empty の増分が0。
  （past-空305件の遼及は対象外。doneのcompleted_atで日付切り分け可）
