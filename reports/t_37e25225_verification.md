# t_37e25225 検証レポート — 失敗垢のリトライ増幅抑制（垢単位サーキットブレーカ＋圏外垢スキップ）

タスク: t_37e25225（root / 是正3件のうち【BOT最優先】の検証・補完）
一次データ: `logs/2026-09-{18..25}/orchestrator_*.log` / `logs/auto_20260924.log` / `logs/auto_20260925.log` / `logs/wifi_watchdog_2026092{4,5}.log`
是正コミット: `4ef200d`（垢単位 failure ceiling・非リトライ分類）/ `c147e6b`（条件2 の追加分岐）
実測窓: before = 2026-09-18 00:00 .. 2026-09-24 09:19（垢単位 ceiling 投入前） / after = 2026-09-24 09:19 .. 2026-09-25 03:40（投入後 18.3h）

## 受入条件の判定（サマリ）

| # | 受入条件 | 判定 | 実測根拠 |
|---|---------|------|---------|
| 1 | リトライ上限を垢単位で実効化（垢ごとに `(account, 時間窓, 失敗回数)` でサーキットブレーカ） | 達成 | `attempts=3`（= 最大3回まで再実行した最終失敗）ライン数 64 → 0。`[CEILING] このサイクルの連続失敗` の最大値 3回(09-19) → 2回(09-24)、09-25 は 0 件 |
| 2 | 圏外垢はリトライせずスキップし、その旨をログに1行残す | 未達（実装は到達不能） | 追加分岐 `applier.py:885-903` は同一入力・同一条件の先行 return（`applier.py:855-871`）に完全に遮蔽されるデッドコード。wifi_watchdog の SSID圏外/電源OFF/バックオフ判定は applier から未参照（`account_wifi_map` を参照する kensho 配下ファイル = 0）。実発動ログ 0 件 |
| 3 | 修正後24hのログで1垢あたりの再実行回数が 3 未満・同一垢の連続 `attempts=3` なし（before/after を数値で） | 達成 | after 窓で `attempts=3` 0 件、`連続失敗` 最大 2 回。数値は `reports/t_37e25225_evidence.json` の outcome に before/after で記録 |
| 4 | 既存の BOT 制約を一切緩めない | 達成 | `max_actions_per_hour: 15` / `max_total_actions_per_day: 100` / `min-max_delay: 15-60s` / `active_hours: 08:00-23:00` / `max_attempts: 3` すべて不変。`4ef200d` の config.yaml 差分はコメント＋`max_pages`＋`recovery_order`＋`fatal_signal_*` 追加のみ（緩和なし） |

総合判定: 条件1・3・4 = 達成、条件2 = 未達（追加分岐は no-op）。

## 条件2 が未達である理由（一次証跡つき）

1. 追加分岐の入力は既存ゲートと同一
   - `applier.py:59` = `from kensho.utils.safety import dead_proxy_reason as _dead_proxy_reason`
   - `applier.py:860` = `_dead = _dead_proxy_reason(cfg, account_key)` → `:861` `if _dead:` で `return (0, 0)`
   - `applier.py:892` = `skip_reason = dead_proxy_reason(cfg, account_key)` → `:893` `if skip_reason:` で `return (0, 0)`
   - つまり条件2の分岐は、直前の dead_proxy ゲートが真にならない限り到達せず、真になれば先行 return 済み。恒久的に実行されない。
2. 条件2が指定した入力（wifi_watchdog の「SSID圏外 or 電源オフ」/ バックオフ中）は使われていない
   - `account_wifi_map`（SSID/アダプタ/信号の実測マップ）を参照する kensho 配下の .py は 0 ファイル（scripts/ 側のみ）。
3. 実発動ログは 0 件
   - `ネットワーク圏外/電源OFF/バックOFF` = 0 行、`プロキシ死骸（` = 0 行（09-24/09-25 の orchestrator + auto ログ）。
4. そもそも圏外垢は applier まで到達しない
   - `zin20120731` は 09-25 に 14 回「垢別起動」されるが、毎回その直後が `処理待ちのバッチなし`（`kensho/orchestrator.py:422`）で、applier は起動されない（収集不能 → 応募対象 0 件）。
   - したがって「圏外垢が応募でリトライを重ねる」経路自体は上位レイヤで既に閉じており、実害は出ていない。条件2の要求は「入力の取り違えにより、既存ゲートと重複した no-op が入った」形になっている。

## 実測に使った再現コマンド

- 計測スクリプト: `reports/t_37e25225_scan.sh`（生出力: `reports/t_37e25225_scan_output.txt`）
- 単体テスト: `tests/test_self_heal.py`（条件1・dead_proxy ゲートの回帰）
- 参照ログ: `logs/2026-09-{18..25}/orchestrator_*.log`（各日 300〜320 バッチ）

## 検証

$ bash reports/t_37e25225_scan.sh && sed -n '20,28p' reports/t_37e25225_scan_output.txt
### 2. attempts=3（self_heal が最大3回まで再実行した最終失敗）ライン数
   2026-09-18 attempts=3 lines: 0
   2026-09-19 attempts=3 lines: 0
   2026-09-20 attempts=3 lines: 0
   2026-09-21 attempts=3 lines: 0
   2026-09-22 attempts=3 lines: 14
   2026-09-23 attempts=3 lines: 50
   2026-09-24 attempts=3 lines: 0
   2026-09-25 attempts=3 lines: 0

$ sed -n '1,19p' reports/t_37e25225_scan_output.txt
### 1. [CEILING] このサイクルの連続失敗: N回 の値分布（= 垢単位の連続リトライ回数）
--- 2026-09-18 (orchestrator 307 files) ---
         4 このサイクルの連続失敗: 1回
--- 2026-09-19 (orchestrator 321 files) ---
         3 このサイクルの連続失敗: 1回
         1 このサイクルの連続失敗: 2回
         1 このサイクルの連続失敗: 3回
--- 2026-09-24 (orchestrator 319 files) ---
         8 このサイクルの連続失敗: 1回
         1 このサイクルの連続失敗: 2回
--- 2026-09-25 (orchestrator 51 files) ---

$ python3 -m pytest tests/test_self_heal.py -q --no-cov
30 passed in 61.07s

$ sed -n '33,54p' reports/t_37e25225_scan_output.txt
### 3. 圏外垢スキップ（条件2）の実発動ログ
   'ネットワーク圏外/電源OFF/バックOFF' 件数 (logs/2026-09-24,2026-09-25, auto_20260924/0925.log): 0
   'プロキシ死骸（' 件数 (logs/2026-09-24,2026-09-25, auto_20260924/0925.log): 0
### 4. 圏外垢 zin20120731 の応募経路（orchestrator のバッチ判定）
   auto_20260925.log の '垢別起動: zin20120731' 回数: 14
     2026-09-25 00:04:18.583 | INFO | kensho.core.logger:write:48 -   垢別起動: zin20120731
     2026-09-25 00:04:18.631 | INFO | kensho.core.logger:write:48 -   処理待ちのバッチなし
### 5. 条件2 実装の到達可能性（同一入力の先行 return に遮蔽されていないか）
   applier.py:59  : from kensho.utils.safety import dead_proxy_reason as _dead_proxy_reason
   applier.py:860 :     _dead = _dead_proxy_reason(cfg, account_key)
   applier.py:861 :     if _dead:
   applier.py:892 :         skip_reason = dead_proxy_reason(cfg, account_key)
   applier.py:893 :         if skip_reason:
     kensho/ 配下で account_wifi_map を参照するファイル数: 0

$ sed -n '55,62p' reports/t_37e25225_scan_output.txt
### 6. BOT制約（rate_limits / max_attempts）が緩められていないか
   264:  max_total_actions_per_day: 100
   265:  max_actions_per_hour: 15
   266:  active_hours_start: "08:00"
   267:  active_hours_end: "23:00"
   268:  min_delay_between_actions: 15
   269:  max_delay_between_actions: 60
   315:  max_attempts: 3

$ git log --oneline -2 -- kensho/core/self_heal.py kensho/application/applier.py
1d2a644 fix(applier): t_64f60f04 _multi_response_record log 汎容化（callable 対応）
4ef200d fix(t_8946706e): self_heal 恒久修正 — failure ceiling の垢粒度化 / セッション失効垢の盲目的リトライ停止（BOTシグナル増幅の停止）

## 申し送り（条件2 の是正）

- 条件2の要求は「wifi_watchdog が SSID圏外/電源OFF/バックオフ中と判定した垢を、応募前にスキップし、その旨を1行ログに残す」。現状は既存 dead_proxy ゲートと同一入力の no-op 分岐。
- 是正の選択肢（実装判断は後続カードへ）:
  1. `data/account_wifi_map.json`（SSID/アダプタ状態の実測）または wifi_watchdog の backoff 状態を入力にした独立ゲートを追加し、`network_outage_skip` を実際に発火させる。
  2. 重複 no-op 分岐を削除し、条件2を「上位レイヤ（orchestrator のバッチ0判定）＋ dead_proxy ゲートで担保」と再定義する。
- 条件1（垢単位サーキットブレーカ）と条件3・4 は本レポートの数値で達成済み。BOT 制約は不変。
- 並行作業の干渉: `scripts/audit_bot_safety.py` に別タスク（t_3f48a43e）の未コミット変更が残っており、`kanban_done_guard.py --task` の条件(d) は本タスク所有パス扱いで BLOCK する（本タスクの作業起因ではない。内容には一切触れていない）。
