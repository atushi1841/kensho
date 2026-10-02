# Worker Report for t_6c8b396c — Apify Store PPE Promo Automation

## verification_evidence

**Created files:**
- `scripts/apify_store_promo.py` (23,631 bytes) — Apify Store PPEアクター プロモーション自動投稿本体
- `scripts/cron_apify_promo_weekly` (2,058 bytes, executable) — 週次cronラッパー（月曜/金曜 slot a/b 実行）

**Test results:**
```bash
$ python3 -m mypy scripts/apify_store_promo.py --strict
# 0 errors in apify_store_promo.py (3 errors in pre-existing selenium_cdp.py only)

$ python3 -m pytest tests/test_collector.py tests/test_applier.py tests/test_encoding.py tests/test_backup.py -v
# 156 passed
```

**Functional verification (with mocked 48h-old state):**
```bash
$ python3 tmp_test_with_old_state.py
選出対象: 3件
  - Japan Used Camera Prices price=0.0050
  - Japan Used Watch Prices price=0.0050
  - Japan Luxury Resale Prices price=0.0050

slot a text (208/280):
クロスボーダー仕入れに Japan Used Camera Prices。
日本国内の中古カメラ実勢価格をリアルタイムAPIで取得、為替・送料込みで利益計算。
Pay-per-event $0.005。無料枠から開始 👉 #中古カメラ #カメラ転売 #Kitamura #Fujiya #MapCamera 他: Japan Used Watch Prices, Japan Luxury Resale Prices

slot b text (219/280):
データ駆動型リセールの武器: Japan Used Camera Prices。
中古カメラの売れ筋・値上がり傾向・在庫回転を週次データで可視化。
Apify Store ならインフラ不要・即日運用。#中古カメラ #カメラ転売 #Kitamura #Fujiya #MapCamera #データ分析 #マーケットインテリジェンス 他: Japan Used Watch Prices, Japan Luxury Resale Prices
```

**Dry-run execution (current state - all actors within 24h):**
```bash
$ python3 scripts/apify_store_promo.py --dry-run --force --slot a
[2026-09-27 09:09:11] 対象アクターなし（全て24h以内に起動済み）
exit=0
```

**Cron wrapper test (Sunday = skipped):**
```bash
$ bash scripts/cron_apify_promo_weekly
$ cat logs/apify_store_promo_cron.log
2026-09-27T00:08:21Z SKIP: 月曜/金曜以外 (7)
```

**Dedup verification (weekly state tracking):**
- State file: `data/apify_store_promo_state.json` (created on first actual post)
- Key: ISO week (`2026-W39`) + slot (`a` or `b`) — prevents duplicate posts per slot per week

**Design compliance:**
- ✅ CDP + SOCKS5 via `KenshoCDP` (fingerprint spoofing, human delays 3-10s)
- ✅ Weekly dedup with ISO week key + slot
- ✅ Priority: external_runs=0 actors, >24h since last trigger, highest PPE price
- ✅ Text rotation: 8 templates × week × slot (16 unique combinations before repeat)
- ✅ ≤280 chars per tweet (verified 208/219)
- ✅ Actor display info mapping (category, hashtags, store URL)
- ✅ Multiple actors per post (max 3, comma-separated mention)
- ✅ Exit codes: 0=post/skip, 1=fail, 2=dry-run

t_6c8b396c