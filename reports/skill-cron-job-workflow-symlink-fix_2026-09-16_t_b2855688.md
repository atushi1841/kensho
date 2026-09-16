# t_b2855688 — cron-job-workflow スキル symlink 許容記述の「実体コピー必須」改訂レポート

日期: 2026-09-16 (JST) / 実施: kensho-worker (run519)
起因: QA 11:12 定期検証（reports/qa_run_2026-09-16_1112.md §2）/ t_fa68dc0c 受け入れ条件④の続き
根拠事故: cronジョブ 352914c18733 (kensho-dm-winner-check) のスクリプト実体が symlink→repo 化により
scheduler.py の path guard（resolve()後の実体が scripts dir 外 → Blocked）に該当、6連続error（9/16 10:00時点）。
修复済み状態: `hermes cron edit 352914c18733 --script kensho-dm-scan.sh`（ラッパパターン）で last_status=ok 実証済み（t_fa68dc0c）。

## 変更対象と変更前後 diff

### 1. kensho-worker（プロファイル: kensho-worker）
ファイル: ~/.hermes/profiles/kensho-worker/skills/software-development/cron-job-workflow/SKILL.md
変更前 md5: 47a11c7e60dbeacad9a7dfe13ad885b8 → 変更後 md5: 477ccadc81f1f1061bc75a919f76cc91

項目1（6項目チェックリスト L252）:
-  - **bare filenameで登録** — `script='foo.py'`（`scripts/` prefix禁止）。実体は `~/.hermes/profiles/<profile>/scripts/foo.py` に置く（repoの `scripts/foo.py` はsymlink元であってschedulerの解決先ではない）
+  - **bare filenameで登録** — `script='foo.py'`（`scripts/` prefix禁止）。実体は `~/.hermes/profiles/<profile>/scripts/foo.py` に**実体コピー必須**。symlink→リポジトリ等scripts dir外は scheduler.py のpath guardがresolve()後の実体を検出しBlockedする（python直executableでもcronだけ発火毎に失敗）。実例: 9/16 dm-winner-check 352914c18733 がsymlink化で6連続error。推奨形は既存ラッパ `kensho-dm-scan.sh` パターン（profile scripts直下にsh実体を置き、内部でrepoスクリプトを絶対path実行）

項目5（L256）:
-  - **repo追跡** — profile scripts直下はgitの管轄外。実体を `git add` してrepo側 `scripts/` に置き、profile側はコピーかsymlinkで一元管理（二重ソース化はQA検出対象）。pre-commitがformatをいじるのでcommit後はrepo→profileへ再コピーしてmd5一致を確認する
+  - **repo追跡** — profile scripts直下はgitの管轄外。実体を `git add` してrepo側 `scripts/` に置き、profile側は**実体コピーで一元管理**（symlink→repoはpath guardにresolve()後の実体がscripts dir外と判定されBlocked、9/16 dm-winner-check実例。要スクリプト変更時はrepo編集→再コピー、または `kensho-dm-scan.sh` のようなprofile直下ラッパsh実体からrepoスクリプトを絶対path実行）。二重ソース化はQA検出対象。pre-commitがformatをいじるのでcommit後はrepo→profileへ再コピーしてmd5一致を確認する

### 2. kensho-sweeps
ファイル: ~/.hermes/profiles/kensho-sweeps/skills/software-development/cron-job-workflow/SKILL.md
変更前 md5: 3baae16dbb083ba712e8a42701c0d90d → 変更後 md5: 1894295a40539fbd832aedcd1447ff73

「落とし穴 > hermes cron create --script はパストラバーサル検査で弾かれる」の解決策行:
-  - **解決策**: ファイルの実体を `~/.hermes/profiles/<profile>/scripts/` に置く。プロジェクト側から編集して `cp` で同期するか、scripts/ をラッパーにし委譲する（選択肢C参照）
+  - **解決策**: ファイルの実体を `~/.hermes/profiles/<profile>/scripts/` に置く（**実体コピー必須、symlink→scripts dir外は不可** — scheduler.py のpath guardがresolve()後の実体を検査するため、python直executableでもcronだけ発火毎にBlockedされる。実例: 9/16 dm-winner-check 352914c18733 がsymlink化で6連続error）。プロジェクト側から編集して `cp` で同期するか、scripts/ 側をラッパーにし委譲する（選択肢C参照、推奨は `kensho-dm-scan.sh` パターン＝profile直下sh実体→内部でrepoスクリプトを絶対path実行）

### 3. kensho-revenue-worker
ファイル: ~/.hermes/profiles/kensho-revenue-worker/skills/software-development/cron-job-workflow/SKILL.md
変更前 md5: be15f8e310d3ab6b2ed6015ca14f626d → 変更後 md5: 3be2bc1e12f9bee9bb1383b62b2d4078

「no_agent スクリプトの解決はジョブのプロファイルの scripts dir に限定される」の symlink 項:
-  - **symlink が規定 scripts dir の外を向くと Block**: 例 kensho-ready-deprecate.sh は resolve() 後 outside → Blocked。
-  - 修正は「実体を規定 scripts dir 内に置く」こと（外への symlink は不可）。
+  - **symlink→scripts dir外は不可（実体コピー必須）**: scheduler.py のpath guardが resolve() 後の実体を検査するため、python直executableでもcronだけ発火毎にBlockedされる。実例: 9/16 dm-winner-check 352914c18733 がsymlink化で6連続error（t_1c52e2f6 と同一根本原因）。
+  - 修正は「実体を規定 scripts dir 内に置く」こと（外への symlink は不可）。推奨形は `kensho-dm-scan.sh` パターン：profile scripts直下にsh実体を置き、内部でrepoスクリプトを絶対path実行する。

## 受け入れ条件実測

`grep -c "symlink→"`（改訂マーカー出現数）:
- kensho-worker: 2（項目1・項目5）✅
- kensho-sweeps: 1 ✅
- kensho-revenue-worker: 1 ✅
- kensho-critic / kensho-qa / kensho-revenue-qa: 0（変更なし）

## 他プロファイルへの展開について（記録）

QA実測でずれていた md5 380da336 版（kensho-critic / kensho-qa / kensho-revenue-qa の3プロファイル共有）は、
t_c6b4e3ed の6項目チェックリストセクション自体を欠く旧構造であり、symlinkを許容する記述は存在しない
（該当箇所なし＝修正不要）。これらプロファイルは本カードの必須対象（worker/sweeps/revenue-worker の3版）
外のため展開せず。将来これらのプロファイルにチェックリストセクションを追加する際は、必ず本改訂版
（実体コピー必須・symlink→禁止文言）を用いること。

なお kensho-worker 版項目3の `__file__` は `realpath` で解決という記述は、profile直下の**実体**ラッパ
内部からのrepoスクリプト参照を指すもので、symlink設定の許容ではない（矛盾なし、維持）。

コード変更なし（スキル文書のみの改訂）。
