# Changelog

## v3.5 (2026-06-24) — 10タスク一括完了

### 追加
- argparse対応: `kensho_collect.py` / `kensho_apply_single.py` が `--help` 対応
- 並列応募: `orchestrator.py` に `ThreadPoolExecutor(max_workers=2)` 導入
- keyring対応: `utils/keyring.py` — Windows Credential Manager に auth_token を安全保存
- applierテスト: 15テスト追加（_is_active_hours, _generate_reply, 日次カウンター, レート制限, 排他ロック）
- CHANGELOG.md 新設
- `--version` フラグ追加
- `core/__init__.py` 整備（短縮import対応）

### 改善
- logs archive: 古い `apply_result_*.json` を `data/archive/` に移行
- 進捗出力: `[3/15] ⏱5分 〆2026-07-01 10000名 https://x.com/xxx...` 形式
- cleanup.py: ユーザーFirefox保護（親プロセスがpythonのものだけkill）
- README: 構成図を実態に同期（encoding/archive/pyproject.toml等）

### 修正
- applier.py: `global_idx` 未定義参照バグ修正
- cron_worker: `//F //IM` → `/F /IM` 統一

---

## v3.4 (2026-06-24) — 9カテゴリ包括修正

### 追加
- `core/encoding.py` — cp932ガード共通ユーティリティ
- `pyproject.toml` + `.python-version` (3.11) + git init

### 修正
- x_url #fragment除去 (`resolve_redirect()` でhash削除)
- `is_x_url()` に `/status/` 必須チェック追加（アカウントページ除外）
- deadline/winners抽出改善（title優先 → expiredatetime-display → tousenST）
- collected.json既存25件の#fragment修復（9件は自動スキップ対象に）
- `except Exception: pass` 全4箇所にtraceback出力追加
- cp932ガード重複を5ファイル→1ファイルに集約
- インラインimport 4箇所をトップレベルに修正
- health.py daemon.pid削除済み参照を修正
- デッドコード削除（shスクリプト2つ, wifi_manager委譲関数）

### テスト
- test_collector: 12→29テスト（deadline抽出9パターン, is_x_url 6パターン）
- test_encoding: 新規3テスト
- 合計32テスト / mypy 0 error

---

## v3.3 (2026-06-24) — 型ヒント+mypy+テスト基盤

### 追加
- 全27ファイルに型ヒント導入完了
- mypy strict mode で 0 error 達成
- pytest 基盤: 20テスト / 0.62秒
- リファレンス: `type-hints-and-mypy.md`, `test-strategy.md`

---

## v3.2 (2026-06-24) — 第二弾15件修正

### 修正
- 🔴 重大3件: psutil未import / checker相対import死 / collect上書きバグ
- 🟡 中5件: task_builder参照 / file参照 / daemon //taskkill / 孤児ファイル削除
- 🟢 軽微3件: 未使用import / reply欠落 / 17死script削除

---

## v3.1 (2026-06-24) — 6パス大改修

### 追加
- 自動バックアップ機構 + 排他ロック + Race Condition対策
- 指紋偽装（垢別WebGL/Canvas/Fonts）
- リプライ機能（15%確率, キーワード別テンプレート）
- 期限収集（deadline/winner_count）
- Wi-Fi安全再接続（Restart-NetAdapter）
- graceful shutdown

### 改善
- UAローテーション（5種類）
- cron→scripts移動
- collected.json detail_url統一
- README刷新, .gitignore作成
- 226MBゴミ削除

---

## v3.0 (2026-06-23) — 初版

- 基本収集＋応募パイプライン
- 4アカウント構成（ForceBindIP IP分離）
- daemon.py 常駐デーモン（keepalive + orchestrator）
- Firefox 指紋偽装（基本）
- レート制限
- Discord/Toast通知
