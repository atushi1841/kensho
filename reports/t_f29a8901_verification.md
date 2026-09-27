# t_f29a8901 — Apify PPE 外部実行の完了検証と実収益確認

## verification_evidence

### 検証方法

Apify REST API `GET /v2/actor-runs/{run_id}` で7件のrun状態を直接確認。
実収益は `scripts/apify_revenue_settle_tracker.py` (live mode) で計測。
外部ユーザーrunの有無は各アクター `/v2/acts/{id}/runs?limit=100` から30日-windowで走査。

### 条件① 7件すべて status=SUCCEEDED — PASS

```
$ python3 /tmp/verify_ppe.py
last_trigger entries: 15
Counter({'2026-09-25': 8, '2026-09-27': 7})

=== RUN STATUS ===
MgekeE2LtJvUDqaCQ: HTTP 200 status=SUCCEEDED exit=0 actor=None
cNgZV15bYpCczUUal: HTTP 200 status=SUCCEEDED exit=0 actor=None
5SzLq38wM7r3Jc5a6: HTTP 200 status=SUCCEEDED exit=0 actor=None
gS7SFa6zLQZ4GcYHA: HTTP 200 status=SUCCEEDED exit=0 actor=None
LdjKH6A34TTwQ6wrT: HTTP 200 status=SUCCEEDED exit=0 actor=None
lsAkzmdbBxNyB9xTq: HTTP 200 status=SUCCEEDED exit=0 actor=None
o6QPlJVZD0gH8IRrl: HTTP 200 status=SUCCEEDED exit=0 actor=None
```

```
$ python3 /tmp/inspect_runs.py
owner id: VMz6nlpHoGIjTeSXS

MgekeE2LtJvUDqaCQ:
  status: SUCCEEDED exit: 0
  userId: VMz6nlpHoGIjTeSXS owner? True
  startedAt: 2026-09-27T03:41:31.683Z finishedAt: 2026-09-27T03:41:45.235Z
  chargedEventCounts: {"apify-actor-start": 1, "apify-default-dataset-item": 100}
cNgZV15bYpCczUUal:
  status: SUCCEEDED exit: 0
  userId: VMz6nlpHoGIjTeSXS owner? True
  startedAt: 2026-09-27T03:41:33.112Z finishedAt: 2026-09-27T03:41:39.991Z
  chargedEventCounts: {"apify-actor-start": 1, "apify-default-dataset-item": 0}
5SzLq38wM7r3Jc5a6:
  status: SUCCEEDED exit: 0
  userId: VMz6nlpHoGIjTeSXS owner? True
  startedAt: 2026-09-27T03:41:34.485Z finishedAt: 2026-09-27T03:41:45.047Z
  chargedEventCounts: {"apify-actor-start": 1, "apify-default-dataset-item": 100}
gS7SFa6zLQZ4GcYHA:
  status: SUCCEEDED exit: 0
  userId: VMz6nlpHoGIjTeSXS owner? True
  startedAt: 2026-09-27T03:41:35.907Z finishedAt: 2026-09-27T03:41:53.823Z
  chargedEventCounts: {"apify-actor-start": 1, "apify-default-dataset-item": 100}
LdjKH6A34TTwQ6wrT:
  status: SUCCEEDED exit: 0
  userId: VMz6nlpHoGIjTeSXS owner? True
  startedAt: 2026-09-27T03:41:37.353Z finishedAt: 2026-09-27T03:41:47.548Z
  chargedEventCounts: {"apify-actor-start": 1, "apify-default-dataset-item": 60}
lsAkzmdbBxNyB9xTq:
  status: SUCCEEDED exit: 0
  userId: VMz6nlpHoGIjTeSXS owner? True
  startedAt: 2026-09-27T03:41:40.241Z finishedAt: 2026-09-27T03:41:46.055Z
  chargedEventCounts: {"apify-actor-start": 1, "apify-default-dataset-item": 24, "mandarake-search": 0}
o6QPlJVZD0gH8IRrl:
  status: SUCCEEDED exit: 0
  userId: VMz6nlpHoGIjTeSXS owner? True
  startedAt: 2026-09-27T03:41:45.255Z finishedAt: 2026-09-27T03:42:29.078Z
  chargedEventCounts: {"apify-default-dataset-item": 30, "apify-actor-start": 2}
```

### 条件② actual_revenue_usd > 0 — FAIL

実収益 $0.000000。7件すべての `userId` が実行アカウント `VMz6nlpHoGIjTeSXS` と一致し、外部ユーザーrun = 0件。
PPE課金は「外部ユーザーのrun」のみが対象で、自アカウントのrunは課金対象外のため、
chargedEventCounts に `apify-default-dataset-item` が発生しても実収益にはならない。

```
$ python3 /tmp/check_external.py
japan-used-camera-market-scraper (mQaZFo6up4YZKepC3): runs_in_30d=15 external=0 charged_items=0 users={'VMz6nlpHoGIjTeSXS'}
japan-watch-market-scraper (gMqdrS2evpcybSZc2): runs_in_30d=14 external=0 charged_items=0 users={'VMz6nlpHoGIjTeSXS'}
japan-luxury-brand-market-scraper (b0vuqa3ESvy2mOwFB): runs_in_30d=14 external=0 charged_items=0 users={'VMz6nlpHoGIjTeSXS'}
japan-used-instrument-market-scraper (yN1R26HrV6C2MBKas): runs_in_30d=14 external=0 charged_items=0 users={'VMz6nlpHoGIjTeSXS'}
japan-offmall-market-scraper (Zh4kqcS4dYPWpFzBd): runs_in_30d=47 external=0 charged_items=0 users={'VMz6nlpHoGIjTeSXS'}
surugaya-japan-hobby-prices (F8Hl0a8Cx9bpJBrxR): runs_in_30d=0 external=0 charged_items=0 users=set()
mandarake-auction-scraper (q2E37PVTg5JcGOTEn): runs_in_30d=4 external=0 charged_items=0 users={'VMz6nlpHoGIjTeSXS'}

TOTAL external runs: 0 charged items: 0
```

### 条件③ settle_rate_pct = 100% — FAIL

- estimated_revenue_usd = $0.035000 (7件 × $0.005)
- actual_revenue_usd = $0.000000
- settle_rate = 0 / 0.035 × 100 = 0.00%

```
$ python3 /tmp/check_settle.py
RC: 0
STDOUT:
 [2026-09-27 09:33:47 UTC] Apify Revenue Settle Tracker start
  Estimated revenue (from latest run): $0.035000
  Triggered actors: 7
  Owner: VMz6nlpHoGIjTeSXS
  Fetching actual revenue for 7 actors...
  Actual revenue: $0.000000 (external_runs=0, charged_items=0)
  Settle rate: 0.00%
✓ state 保存: /mnt/d/Project2/kensho/data/apify_settle_state.json

=== Apify Revenue Settle Tracker Summary ===
Estimated: $0.035000
Actual:    $0.000000
Settle:    0.00%
Window:    30 days
Mode:      live
```

## 結論

実行は7件完了したが、**実収益は発生していない**。
成功指標のうち①は達成、②③は未達。タスクの完了条件（実収益>0, settle 100%）を満たさない。

## 次のステップ（タスク本文記載の代替案）

1. quota回復後（翌日以降のリセット）に `scripts/apify_ppe_external_runner.py` を再実行
2. quota超過3Actorは手動リクレジット化（Apify Console → Billing → top-up）

## 証跡ファイル

- `data/evidence_t_f29a8901.json` — 構造化証拠（API生応答）
- `data/apify_settle_state.json` — settle履歴（latest エントリ）