# QA検証レポート: t_d5ac9f32 DeepSeek鍵ローテーション done_guard 準拠確認

- QA実行タスク: t_8e1e4934 (assignee: kensho-qa)
- 検証対象: t_d5ac9f32 (kensho-revenue-worker) の証跡 `reports/t_d5ac9f32_verification.md`
- 実施日時: 2026-09-23 20:57〜21:14 JST
- 一次判定ツール: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py` (repo外・閲覧のみ)
- 禁止領域遵守: DEEPSEEK_API_KEY の完全形は一切出力していない（末尾4桁のみ）。`config.yaml` の default/provider/model は未変更（本QAはファイル変更を行っていない）。

## 判定サマリ（t_8e1e4934 の実測に基づく）

| # | 検証条件 | 判定 | 根拠（実測） |
|---|---|---|---|
| 1 | `## verification_evidence` 見出し + dominant-id = t_d5ac9f32 | PASS | guard `own_file=true` / `owner_task_id=t_d5ac9f32` |
| 2 | `$ cmd` 形式のコマンド引用 >= 3件 | PASS | guard `citations_count=5`（独立grepでも5行） |
| 3 | git に未コミットコードが無い（camera_7d_aggregate.py 以外） | **FAIL** | `kensho/scraping/collector.py` が未コミット（後述: 対象タスク完了後の外部編集） |
| 4 | backup_dir に .env バックアップ5件 | PASS | 5ファイル実在（kensho-critic/qa/worker/revenue-qa/revenue-worker） |
| 5 | 各プロファイル .env の鍵末尾4桁 = 4e70 | PASS | 5/5 `key_suffix=4e70`、バックアップ側は旧鍵 570d |
| 6 | curl で 5プロファイル HTTP 200 | PASS | 5/5 が 200 到達（401/403 は0件） |

総合: 対象タスク t_d5ac9f32 の証跡条件 (1)(2) は再現、ローテーション実体 (4)(5)(6) も QA が独立に PASS。
ただし **条件3 のみ現時点で FAIL** のため、t_8e1e4934 が guard を再実行した結果は `pass=false`（理由は (d) 単独）。

## verification_evidence

本節は QA実行タスク t_8e1e4934 が実行した実コマンドの出力コピーである（t_8e1e4934 の所有証跡）。

### V1. done_guard 一次判定（条件1・2・3の再現） — t_8e1e4934 実行
$ python3 /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_d5ac9f32 --json
{"task_id": "t_d5ac9f32", "output_file": "/mnt/d/Project2/kensho/reports/t_d5ac9f32_verification.md", "conditions": {"a:verification_evidence_section": true, "b:command_citations>=3": true, "c:no_false_done_marker_in_summary": true, "d:no_uncommitted_code": false, "e:pushed_and_hashes_ancestor": true, "f:no_dep_drift": true, "g:evidence_durable": true, "h:result_nonempty": true, "i:cron_config_md5_matches": true, "j:evidence_json_valid": true, "k:outcome_review": true}, "detail": {"citations_count": 5, "summary": "early_complete: commit 0b7fc91 pre-existing (rotation ff1c62e) — DeepSeek key rotation verified HTTP 200 x5; done_guard now PASS on own evidence report.", "uncommitted_code_files": ["kensho/scraping/collector.py"], "foreign_uncommitted_code_files": [], "d_scope": "repo", "owner_task_id": "t_d5ac9f32", "own_file": true, "e_status": "ok", "e_note": "1 unpushed commit(s) touch docs/data only — allowed | hashes: 1 hash(es) cited, 0 invalid", "e_soft": false, "f_status": "skip", "f_drift_count": 0, "f_note": "cached (739s ago): No broken requirements found.", "f_soft": false, "g_status": "pass", "g_uncommitted": [], "g_note": "evidence tracked: reports/t_d5ac9f32_verification.md (durability: in-repo)", "g_soft": false, "g_hard": true, "h_status": "pass", "h_note": "tasks.result non-empty", "h_soft": false, "h_hard": true, "i_status": "ok", "i_fails": 0, "i_note": "drift=0 missing=0", "i_hard": true, "i_soft": false, "j_status": "skip", "j_path": null, "j_missing_fields": [], "j_missing_artifacts": [], "j_note": "no evidence.json found (markdown path retained)", "j_hard": true, "j_soft": false, "k_status": "skip", "k_note": "no numeric KPI in success_indicators (outcome review not applicable)", "k_hard": false, "k_soft": false, "unpushed_hashes_allowed": [], "e_hard": true, "f_hard": true}, "pass": false}
EXIT=1

→ t_8e1e4934 の読み: 条件1(a)/2(b) は true、citation 数=5（>=3）。false は (d) のみで、原因は `kensho/scraping/collector.py` の未コミット .py。

### V2. 証跡ファイルの見出し・引用の独立確認 — t_8e1e4934 実行
$ search_files pattern='^\s*\$\s*%?\s*\S+' path=reports/t_d5ac9f32_verification.md
6: $ python3 inspect_deepseek_env.py
22: $ python3 check_deepseek_candidate.py
27: $ python3 rotate_deepseek_key.py
32: $ python3 verify_deepseek_rotation.py
37: $ for p in kensho-critic kensho-qa kensho-worker kensho-revenue-qa kensho-revenue-worker; do python3 verify_one_profile.py "$p"; done

→ 各行の直後行に実出力（または `→` 行）があり、guard の v57 規則（実出力ゼロの `$ cmd` は不計上）を満たすと t_8e1e4934 が確認。見出しは3行目 `## verification_evidence`（行末まで空白のみ）。

### V3. 未コミットコードの検査（条件3 FAIL の実測根拠） — t_8e1e4934 実行
$ git status --porcelain -uall | grep -E '\.(py|yaml|sh|js)$' | grep -v '^.. data/' | grep -v '^.. reports/'
 M kensho/scraping/collector.py
$ stat -c '%n %y' kensho/scraping/collector.py
kensho/scraping/collector.py 2026-09-23 20:37:41.711834600 +0900
$ git log -1 --format='%h %cI %s' 0b7fc91
0b7fc91 2026-09-23T19:24:57+09:00 t_d5ac9f32: shorten sha256 digest in evidence for dominant-id binding
$ git status --porcelain config.yaml
(出力なし = config.yaml 未変更)

→ 未コミットコードは1件のみ（`kensho/scraping/collector.py`）。mtime 20:37 は対象タスク完了コミット 0b7fc91 (19:24) より 73分後 → 対象タスク自身の作業ではなく、**完了後に第三者プロセス/別タスクが残した編集中ファイル**。diff は `1b55c7d`(t_c5097d30) が入れた引数なし lambda の TypeError 回帰修正（`partial(scrape_kenkaku, proxy=_kensho_proxy)` + out/ps/ak の位置引数化）。
なお条件3で例外扱いされていた `scripts/camera_7d_aggregate.py` は既に追跡済み（`git ls-files` で確認）で、未コミットではない。guard の (d) は repo-wide スコープ（`d_scope=repo`）なので、この1ファイルが全タスクの done を止める。

### V4. バックアップ5件と「鍵行のみ原子置換」の検証（条件4・5） — t_8e1e4934 実行
$ ls -1 /home/atushi/.hermes/profiles/.deepseek-key-backups-20260923T094106Z/
kensho-critic.env
kensho-qa.env
kensho-revenue-qa.env
kensho-revenue-worker.env
kensho-worker.env
count=5
$ python3 qa_backup_diff.py
{"rows": [{"profile": "kensho-critic", "backup_keys": 25, "current_keys": 25, "changed_key_names": ["DEEPSEEK_API_KEY"], "only_key_line_changed": true, "backup_key_suffix": "570d", "current_key_suffix": "4e70", "key_value_differs": true}, {"profile": "kensho-qa", "backup_keys": 25, "current_keys": 25, "changed_key_names": ["DEEPSEEK_API_KEY"], "only_key_line_changed": true, "backup_key_suffix": "570d", "current_key_suffix": "4e70", "key_value_differs": true}, {"profile": "kensho-worker", "backup_keys": 25, "current_keys": 25, "changed_key_names": ["DEEPSEEK_API_KEY"], "only_key_line_changed": true, "backup_key_suffix": "570d", "current_key_suffix": "4e70", "key_value_differs": true}, {"profile": "kensho-revenue-qa", "backup_keys": 26, "current_keys": 26, "changed_key_names": ["DEEPSEEK_API_KEY"], "only_key_line_changed": true, "backup_key_suffix": "570d", "current_key_suffix": "4e70", "key_value_differs": true}, {"profile": "kensho-revenue-worker", "backup_keys": 27, "current_keys": 27, "changed_key_names": ["DEEPSEEK_API_KEY"], "only_key_line_changed": true, "backup_key_suffix": "570d", "current_key_suffix": "4e70", "key_value_differs": true}], "all_only_key_line_changed": true, "all_keys_rotated": true, "all_backup_suffix_570d": true, "all_current_suffix_4e70": true}

→ バックアップは旧鍵 …570d、現行は …4e70。各 .env で変化したキー名は `DEEPSEEK_API_KEY` のみ（他25〜27キーの値は不変）＝証跡の「non_key_lines_unchanged / 原子 temp-replace」を t_8e1e4934 が独立に確認。鍵の完全形は出力していない。

### V5. 5プロファイル実 curl 再検証（条件6） — t_8e1e4934 実行
$ python3 qa_final_evidence.py
{"profiles": [{"profile": "kensho-critic", "key_suffix": "4e70", "key_len": 35, "attempts_to_200": 2, "codes": ["000/rc28", "200/rc0"], "http_200_reached": true}, {"profile": "kensho-qa", "key_suffix": "4e70", "key_len": 35, "attempts_to_200": 1, "codes": ["200/rc0"], "http_200_reached": true}, {"profile": "kensho-worker", "key_suffix": "4e70", "key_len": 35, "attempts_to_200": 1, "codes": ["200/rc0"], "http_200_reached": true}, {"profile": "kensho-revenue-qa", "key_suffix": "4e70", "key_len": 35, "attempts_to_200": 1, "codes": ["200/rc0"], "http_200_reached": true}, {"profile": "kensho-revenue-worker", "key_suffix": "4e70", "key_len": 35, "attempts_to_200": 1, "codes": ["200/rc0"], "http_200_reached": true}], "all_keys_suffix_4e70": true, "all_reached_200": true, "any_401_403": false}

→ 5/5 が `https://api.deepseek.com/v1/models` で HTTP 200 到達、401/403 は0件。kensho-critic の1回目 `000/rc28` は curl の接続タイムアウト（rc=28）で、**認証エラーではない**（V6 で切り分け）。

### V6. タイムアウトの原因切り分け（000 を鍵の失敗と誤判定しないため） — t_8e1e4934 実行
$ python3 qa_curl_diag.py
== A. 認証なし GET (接続性のみ) ==
  noauth#0 http=401 rc=0 err=
  noauth#1 http=401 rc=0 err=
  noauth#2 http=000 rc=28 err=
== B. 各プロファイル鍵 curl (2回, 間に3s) ==
  kensho-critic #0 http=200 rc=0 suffix=4e70 err=
  kensho-critic #1 http=200 rc=0 suffix=4e70 err=
  kensho-qa #0 http=200 rc=0 suffix=4e70 err=
  kensho-qa #1 http=200 rc=0 suffix=4e70 err=
  kensho-worker #0 http=200 rc=0 suffix=4e70 err=
  kensho-worker #1 http=000 rc=28 suffix=4e70 err=
  kensho-revenue-qa #0 http=000 rc=28 suffix=4e70 err=
  kensho-revenue-qa #1 http=000 rc=28 suffix=4e70 err=
  kensho-revenue-worker #0 http=000 rc=28 suffix=4e70 err=
  kensho-revenue-worker #1 http=200 rc=0 suffix=4e70 err=

→ **無認証リクエストでも 000/rc=28（タイムアウト）が発生**。したがって 000 は鍵の無効ではなく WSL 側の間欠的ネットワーク遅延。t_8e1e4934 の結論: 単発 curl の 000 を FAIL と解釈してはならず、リトライ必須。

### V7. guard 自体の健全性確認（判定ツールの妥当性） — t_8e1e4934 実行
$ python3 /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest
SELFTEST OK: (e) unpushed/ghost-hash detection works; (d) task-scoped bleed fix works; (g) evidence durability gate works; (h) result-column gate works; (i) cron-config-drift gate works; (j) evidence.json write+validate round-trip works; (k) outcome-review before/after gate works
SELFTEST_EXIT=0

→ V1 の `pass=false` は guard の故障ではなく、実測どおり (d) が赤であることによるもの。

### V8. 対象タスクのコミット確認 — t_8e1e4934 実行
$ git log --oneline -3
0f5191a t_27c0d656: 証跡の見出しをguard仕様(行末まで空白のみ)に是正 + evidence.json再生成
19aacc7 t_27c0d656: treg登録条件・転換率の実測調査（LLMコスト最適化は非適用と確定）
ab01c01 reports: t_31779dfc non-API revenue evaluation (Benchmark Heaven / JevBench) -> reject
$ git show --stat 0b7fc91
 reports/t_d5ac9f32_verification.md | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)
$ git ls-files --error-unmatch reports/t_d5ac9f32_verification.md
reports/t_d5ac9f32_verification.md

→ 対象タスクのコミット 0b7fc91 は証跡 md の1行のみを変更（コード変更なし）で、証跡は追跡済み（guard (g) `evidence tracked` と一致）。

## 改善ノート（t_8e1e4934 からの申し送り）

1. **[P1] repo-wide な done_guard (d) が未コミット `kensho/scraping/collector.py` で赤** — 2026-09-23 20:37 更新の第三者編集（所有者不明・diff は `1b55c7d`/t_c5097d30 の TypeError 回帰修正）。作業ツリーに残る限り**全タスク**の done 宣言が (d) で止まる。所有者は速やかにコミットするか、破棄するなら `git checkout --` で戻すべき。担当推定: collector.py の直近コミット主（kensho-revenue-worker 系）。
2. **[P2] DeepSeek 疎通の単発 000 を FAIL 扱いしない** — 無認証リクエストでも rc=28 が出るため、鍵検証スクリプトは 3〜5回リトライ + `401/403` 判定で行う（今回 t_8e1e4934 はこの方式で 5/5 の 200 を確認）。
3. **[P3] 証跡の sha256 表記ゆれ** — `reports/t_d5ac9f32_verification.md` は 33行目 `sha256_trunc: 448a...b15b2`（全体の先頭4+末尾4）と 34行目 `sha256=448a...fb4a...b2` の2表記が併存。機密は漏れていないが、読み手が同一値と誤解しないよう統一が望ましい（修正は所有者判断・軽微）。
4. **[P4] 条件3の例外規定のずれ** — カードの条件3は `scripts/camera_7d_aggregate.py` を例外としているが、同ファイルは既に追跡済みで未コミットではない。実測の例外（唯一の未コミット）は `collector.py` であり、次回カードでは「未コミットコード一覧は guard --json の `uncommitted_code_files` をそのまま引用する」運用にすると乖離が防げる。

## 付録: t_8e1e4934 が使用した実測スクリプト（scratch workspace 内・repo変更なし）
- `/home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_8e1e4934/qa_final_evidence.py`
- `/home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_8e1e4934/qa_backup_diff.py`
- `/home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_8e1e4934/qa_curl_diag.py`
- `/home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_8e1e4934/qa_verify_deepseek_rotation.py`
- `/home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_8e1e4934/qa_board_probe.py`
