# t_031f04b9 — kanban_done_guard.py 要約証跡

## 調査対象
`/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py`
- 2694 行 / 136,156 bytes
- sha256: `dd76bd97efa97030255012d19efa28b6666a1d9a654b764d0172b720fdd72cfb`
- polyglot header (sh/python): `bash script.py` / `python3 script.py` / `./script.py` すべて動作

## 役割
`kanban complete` 発行前に実行し、done 条件を 13 条件検査して exit 1 で BLOCK するガード。
虚偽 done（実測エビデンスなし・未コミットコード残し・result 空など）の恒久対策。

## 判定条件（13 条件）

| 条件 | 内容 | hard 化日 |
|------|------|-----------|
| a | worker 出力に `verification_evidence`（or 検証/実測/エビデンス）見出しセクション存在 | 常時 |
| b | 同セクション内にコマンド出力引用が 3 件以上（`$ cmd` 行 / フェンス内行 / `→` 行） | 常時 |
| c | summary に虚偽 done マーカー（虚偽/done→blocked/書き換え 等）が無事 | 常時 |
| d | git working tree に未コミットコード（*.py/*.yaml/*.sh/*.js）が無事。v79 でタスク所有ファイル限定に可変 | 常時 |
| e | 受け入れコミットが push 済み（origin/main..HEAD==0）+ 引用ハッシュ ancestry | E_HARD_AFTER |
| f | declared deps vs venv drift（check_dep_drift.py） | F_HARD_AFTER |
| g | 証跡レポートの git 追跡（永続化）。v91 で repo 外証跡の自動コピー追加 | G_HARD_AFTER |
| h | tasks.result 非空（pre_tool_call hook では proposed ペイロードで判定） | H_HARD_AFTER |
| i | cron 配置 md5 一致（enabled DRIFT/MISSING 検出時 cp 同期強制） | I_HARD_AFTER（投入即日 hard） |
| j | 機械可読 evidence.json 整合性（必須フィールド欠落0 / 成果物実在 / hash 形式） | J_HARD_AFTER |
| k | Outcome Review: before/after 数値 KPI 比較 | K_HARD_AFTER |
| bind | 証跡 artifact_paths × 自タスク diff の結線（t_07945937） | BIND_HARD_AFTER |

soft/hard 移行期間: soft 期内は fail でも警告のみで pass 判定に影響しない。期限过了以降 exit 1 で BLOCK。

## 主要 API

### `evaluate(task_id, output_dirs, db_path, workdir, allow_unpushed, task_scoped_d, proposed) -> dict`
全条件を評価し `{task_id, output_file, conditions{...}, detail{...}, pass}` を返す。
`pass = all(conditions.values())`

### `write_evidence(task_id, workdir, payload) -> (int, str)`
条件(j) の生成側 API。`reports/<task_id>_evidence.json` を書く。
payload は `success_indicators / verification_commands / artifact_paths / evidence_hashes` の 4 リストが非空必須。
成果物パス実在を事前確認し、書直後で `evidence_json_state` 再検証して整合性保証。

### `evidence_json_state(workdir, task_id, search_dirs) -> dict`
- pass: 存在・有効JSON・必須フィールド欠落0・成果物パス全て実在
- fail: JSON 不正 / 欠落>0 / 実在不成立 / hash 形式不正 / プレースホルダ語
- skip: ファイル未検出（markdown 証跡経路維持・additive）

必須フィールド: `task_id, status, success_indicators, verification_commands, artifact_paths, evidence_hashes`

## CLI フラグ
`task_id` (positional or `$HERMES_KANBAN_TASK`) + `--soft` `--json` `--db` `--output-dirs` `--workdir` `--allow-unpushed` `--task` `--completion-payload` `--selftest` `--selfcheck` `--write-evidence` `--payload` `--payload-file`

## 詳細実装参照
- `_verification_section_start`: 末尾に近い `verification_evidence`/検証/実測/エビデンス見出し行の開始 index
- `count_command_citations`: v57 でフェンス散文ブラッド_spot 閉鎖。`$ cmd` 単独は実出力ゼロで不計上
- `owns_file`: 見出し存在 + dominant-id 規則 + evidence binding（cross-task bleed 除去 v47）
- `body_path_tokens`: タスク body から所有パス候補抽出。変更禁止系マーカー行のトークンは除外（t_f8a8b8d3 事故対策）
- `task_owned_paths`: git log --grep=<task_id> + body パスから所有パス集合を算出。判定不能は None（repo-wide fail-safe）

## 証跡生成
`--write-evidence` 実行済み: `/mnt/d/Project2/kensho/reports/t_031f04b9_evidence.json`
sha256: `1c0468f3778ba69034bdf3f9e3f70462beee113e8f5c6cda2ca42b46a0749ee9`