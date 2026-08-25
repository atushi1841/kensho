# 改善ノート: 2026-08-25

Kensho AI自己改善ループ（Critic → Worker → QA）の中間記録。
nightly-critic（4baf143523e0, 2026-08-25 13:57実行）の提案のうち、**危険度「低」** の2件をWorkerが実装。

## Criticの分析結果（低リスク提案のみ抜粋）

### [低] follow_state.json テスト汚染の修正（state_path引数を追加）
- 問題: テストがグローバルパッチ（_STATE_PATH差し替え）で本番ファイル `data/follow_state.json` にテストデータ（acct1/ownerY）を書き込み、本番フォロー記録を消失 → 過フォロー抑止が無効化
- 提案: FollowStateManagerに `state_path` 引数追加、テストは `tmp_path` を渡す

### [低] nightly-critic cron スクリプトパスの修正
- 問題: cronジョブ `nightly-critic` の `script: "kensho/tools/daily_pipeline_report.py"` が存在しないパス（プロファイルscripts/配下に解決される）→ 「Script not found」で失敗
- 提案: プロファイルscripts/にラッパー `kensho-daily-pipeline-report.sh` を作成し、jobs.jsonのscriptフィールドを修正

## Workerの実装内容

### 1. follow_state.json テスト汚染修正 — コミット dda9782 で実装済み（本セッションで検証）
- `kensho/application/follow_state_manager.py`: `__init__` に `state_path: Path | None = None` 引数を追加し、`_load()`/`_save()` は `self._state_path` を使用（デフォルトは従来の `_STATE_PATH`）
- `tests/test_follow_state.py`: グローバルパッチ（try/finallyの`_STATE_PATH`差し替え）を廃止し、`FollowStateManager(account, state_path=tmp_path / "follow_state.json")` に変更
- `data/follow_state.json`: テストゴミを削除し本番データのみに復元

### 2. nightly-critic cron スクリプトパス修正 — 本セッションで実装
- 新規作成: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-daily-pipeline-report.sh`
  - `/home/atushi/kensho-venv/bin/python` で `/mnt/d/Project2/kensho/kensho/tools/daily_pipeline_report.py` を呼ぶ薄いラッパー（引数透過、デフォルト=昨日JST）
- 修正: `/home/atushi/.hermes/profiles/kensho-sweeps/cron/jobs.json` line 588
  - `"script": "kensho/tools/daily_pipeline_report.py"` → `"script": "kensho-daily-pipeline-report.sh"`

## QAの検証結果

- pytest: `uv run python -m pytest tests/ -q --ignore=tests/test_invisible_playwright.py` → **121 passed, 4 skipped**（44.91s）
- テスト汚染の再発確認: `data/follow_state.json` のMD5がテスト実行前後で一致（bb7d51066e6904c76e01826d48b2fd16）。テストゴミ（acct/ownerX/ownerY/test_acct）0件。本番アカウント（zin20120731/kudou/atushi16）の記録のみ
- ラッパー動作: 引数なし実行で昨日（2026-08-24）JSTのレポート生成、exit 0・stderrなし。特定日指定（2026-08-25）も正常
- jobs.json: 編集後もJSONとして妥当、該当行は `"script": "kensho-daily-pipeline-report.sh"` を確認
- git: リポジトリ内変更なし（修正対象はプロファイル外部ファイルのためコミットなし）

## 次回への申し送り

- Critic提案 [高] follow_state（applier.py UIフォールバックフォロー経路への record_follow 追加, line 950 do_follow）は未実装（実行ロジック変更＝高リスクのため保留）
- Critic提案 [中] TankanNotesプロキシ1085復旧（物理操作）、[中] 収集プール鮮度改善、[低→保留] いいねアクションのバランス回復（skip_like周辺、実行ロジック変更のため保留）
- 注意: 過フォローBOTシグナルは8/24レポートで41件検出（上限4回/日超過）。follow_stateの抑止は8/25分から有効化される見込み → 8/26朝のレポートで減少確認を推奨

---

## 【第2サイクル】夜間critic再注文（15:17 JST生成）の低リスク提案の実装

対象データ: 2026-08-24 日次レポート（同一日の2回目の分析）。提案5のみ「低」。

### 提案5（低）: atushi16 過集中2回（08/13時台に各16成功 > 上限15）への対応
- 実装: `config.yaml` atushi16 の 全10バッチ `max: 12 -> 10`（コミット 2962cf8）
- 根拠: kensho-administration技量が推奨するBOT安全ライン `max_n=10` に統一。10バッチ×10=100件/日（目標75は維持）
- 実測による診断修正: 過集中の**主因はバッチ間隔不足ではない**（現行間隔は82〜120分で既に70分以上を充足）。実態は1バッチ内で同一主催者への過フォロー（08-24朝のKOS_PR 8回フォロー＝同一tweetにfollow+rt両成功）による1時間あたり成功数の水増し。この過フォローはコミットdda9782のFollowStateManager上限（2回/日）修正で解消見込みのため、本max_n変更は最大成功数を24→20へ低減する補完策
- 検証: `python3 /tmp/validate_config.py` → YAML妥当、間隔全部>=70分、キャパシティ100。pytest 121 passed / 4 skipped（42s）。pre-commit（check yaml含む）Passed
- git: `2962cf8`

### 申し送り（実装しない提案）
- 提案1【高】TankanNotes応募ゼロ調査/復旧 — 物理操作＋セッション再取得が必要。深夜実行外のため保留
- 提案2【高】過フォロー38件のapplier実効ガード — 実行ロジック変更（高リスク）のため保留。ただし根因（follow_stateテスト汚染）はdda9782で修正済み
- 提案3【中】多重アクション（inobase1-4 like+rt）のskip_like経路確認 — applier実行ロジック変更のため保留
- 提案4【中】エラー率60%低減（stale判定/重複再試行抑止） — applier実行ロジック変更のため保留

### 重要観察（次回criticへ）
- 過集中シグナルの残存は「同一tweetへのfollow+rt両成功」が1時間内に積み重なる構造が主因。15/時以内を厳密に保証するには、応募ロジックでfollow-only/rt-onlyのセッション分離（プロジェクトの「1セッション1種類」ルール）が必要 → 高リスク変更として申し送り
- 8/24レポートのBOTシグナル41件は同日データの再集計であり、dda9782適用後の改善（8/25実績）は翌レポートで測定されるべき
