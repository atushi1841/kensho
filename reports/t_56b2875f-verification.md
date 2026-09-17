# t_56b2875f — KENKAKU源ConnectTimeout対策 検証レポート（early_complete）

タスク: KENKAKU源のConnectTimeout対策 — fallback源切替+再試行ロジック
判定: early_complete — 受け入れ条件を満たす実装は既存コミット（retry=7448138・fallback源切替/再復帰=b057f73）で
      pre-existing。本タスクで新規コード変更なし。

## 結論
提案の3要素はすべて既に実装済みであり、実測でも成功指標を達成している。

1. **ConnectTimeout時のauto_retry** → kenkaku.py v144 (commit 7448138)
   - `_KENKAKU_MAX_RETRIES=3`, `_KENKAKU_RETRY_BACKOFF=2.0`（指数バックオフ 2/4/8s）
   - fetchのみリトライ、非200は即スキップ。恒久テスト tests/test_kenkaku_retry.py（10件、QA受け入れ済み）
2. **3回連続失敗で源を一時skip＋他源(KCLUB/CPMK)で補完** → source_health.py (commit b057f73)
   - collector.py `guarded_source()` が threshold 超のソースを自動skipし他源は独立継続。キャッシュ=既収集分維持。
3. **KENKAKU復帰検知で自動re-add** → 成功時 `record_success()` が consecutive_failures を0へリセット、日跨ぎで日次ロール。

## 実測（今日 logs/collect_20260918_030001.log）
- ConnectTimeout 1件 → リトライ成功（`リトライ1/3（2s待ち）`→ 計17件取得・欠損なし）
- 成功指標「KENKAKU ConnectTimeout 4件/day → 1件/day以下」= 達成（1件/day）
- 収集欠損なし（17件取得）→ 「収集欠損率50%削減」達成見込み

## verification_evidence

$ git merge-base --is-ancestor 7448138 HEAD && echo "retry commit ancestor"
→ YES 7448138 ancestor

$ git merge-base --is-ancestor b057f73 HEAD && echo "health-monitor commit ancestor"
→ YES b057f73 ancestor

$ grep -hc ConnectTimeout logs/collect_20260918_030001.log
→ 1

$ grep -hE "KENKAKU" logs/collect_20260918_030001.log | head -3
→   [KENKAKU] ページ1045100020: ConnectTimeout → リトライ1/3（2s待ち）
→   [KENKAKU] 計17件取得

$ git status --porcelain kensho/scraping/sources/kenkaku.py kensho/scraping/source_health.py kensho/scraping/collector.py tests/test_kenkaku_retry.py
→ (空 — 関連ファイルはコミット済み・クリーン)

（注）カード検証コマンドが対象にする logs/auto_20260918.log はapplyログ。収集は専用cronのため
   collect_20260918_030001.log に出力され、そこでの ConnectTimeout は1件/day（自動applyログ為0件は正常）。
