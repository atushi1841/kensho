# verification_evidence — t_3e17e927

revenue-daily.json 騰度鵞を loop_health.sh に組み込み、自動検知・アラート化

## 変更

`scripts/loop_health.sh` の bash ブロック（240-247行目）+ python heredoc 内に
revenue_record_reconcile.py --check の結果を組み込み、DIVERGED 検出時に
`revenue_diverged_count` を JSON 出力に追加し、score から 20 を減点する。

### 修正点

1. **NameError クラッシュの修正**: `_diverged_count` の減点処理が
   `score = 100`（336行目）の**前**にあった（260行目）ため、
   DIVERGED 検出時に `NameError: name 'score' is not defined` で
   loop_health 全体が analysis failed になる問題を修正。`score = 100` の
   **後**に移動した。

2. **JSON スキーマ追加**: 出力 JSON に `revenue_diverged_count` を追加。
   旧来の `score`/`streak`/`running`/`blocked` 等は一切不変。

## 検証

$ python3 scripts/revenue_record_reconcile.py --check
revenue-reconcile OK entry_date=2026-10-08 state_date=2026-10-08 — 記録とライブstateは一致
EXIT=0

$ timeout 120 bash scripts/loop_health.sh 2>/dev/null | grep -o '"revenue_diverged_count"[^,]*'
"revenue_diverged_count": 0

$ timeout 120 bash scripts/loop_health.sh 2>/dev/null | grep -o '"score"[^,]*'
"score": 79

### DIVERGED パスの確認（意図的乖離注入・後で元に戻す）

$ python3 /tmp/probe_diverge.py
RECONCILE: revenue-reconcile DIVERGED entry_date=2026-10-08 state_date=2026-10-08 keys=[login_ok] collectors_mismatch=True
loop_health exit 0
diverged_count= 1 score= 59
restored

- DIVERGED 検出時: `revenue_diverged_count=1`、score 79→59（-20）、NameError なし、exit 0
- 乖離なし時: `revenue_diverged_count=0`、score 79、スコアに影響なし

## 成功指標

- loop_health.sh 出力に `revenue_diverged_count` が含まれる
- DIVERGED 検出時に score が 20 減点し、0 の場合は影響なし
- NameError で analysis failed にならない（loop_health exit 0 を維持）

## 失敗時代替

`python3 scripts/revenue_record_reconcile.py --apply` で手動復旧。