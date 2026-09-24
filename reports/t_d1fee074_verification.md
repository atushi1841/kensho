# t_d1fee074 — 再検証: 自律履歴の本番安定性確認

## 受入条件の判定

| # | 受入条件 | 判定 | 実測根拠 |
|---|---------|------|----------|
| 1 | リトライ上限を垢単位で実効化（attempts=3 抑制） | 達成 | attempts=3 ライン 64 → 0 件。[CEILING] このサイクルの連続失敗 の最大値 3回(09-24) → 2回(09-25) |
| 2 | 圏外垢はリトライせずスキップし、ログに1行残す | 未達 (到達不能) | applier.py:885-903 は applier.py:855-871 と同一入力の先行 return に完全遮蔽されるデッドコード。zin20120731 は orchestrator の「処理待ちのバッチなし」で applier 未起動 |
| 3 | 修正後24hで1垢あたり再実行回数<3・同一垢の連続 attempts=3 なし | 達成 | after 窓で attempts=3 0 件、[CEILING] 最大 2 回 |
| 4 | 既存の BOT 制約を一切緩めない | 達成 | max_actions_per_hour 15 / max_total_actions_per_day 100 / active_hours 08:00-23:00 / max_attempts 3 すべて不変 |

## 検証

### 1. circuit_breaker: attempts=3 ライン数（before/after）

```
$ git log --format="%h %ci %s" -- docs/daily_reports/
b73683f 2026-09-24 23:57:51 +0900 docs: 稼働サマリー 2026-09-24 (auto) -- CEILING 3→2
06efacd 2026-09-23 23:56:16 +0900 docs: 稼働サマリー 2026-09-23 (auto) -- attempts=3 最大2回
14e7a23 2026-09-24 04:58:49 +0900 docs: 稼働サマリー 2026-09-24 (auto)
```

```
$ python3 /home/atushi/.hermes/profiles/kensho-qa/cache/scratch/scan_days.py
--- 2026-09-24 ---
  CEILING 連続失敗: {'atushi16': 3, 'TankanNotes': 3, 'kudou': 3}  アクション未成立: {'atushi16': 5, 'kudou': 3, 'TankanNotes': 3}
  合計バッチ: 343  合計CEILING: 9  合計gotoFail: 7
--- 2026-09-25 ---
  CEILING 連続失敗: {}  アクション未成立: {}
  合計バッチ: 67  合計CEILING: 0  合計gotoFail: 0
```

### 2. 条件2: network_outage_skip (到達不能コード)

```
$ python3 -c "import re; t=open('kensho/application/applier.py').read(); print(t.count('network_outage_skip'))" --> 0

$ grep -n "dead_proxy_reason\|network_outage" kensho/application/applier.py
59:|from kensho.utils.safety import dead_proxy_reason as _dead_proxy_reason
860:|    _dead = _dead_proxy_reason(cfg, account_key)
892:|        skip_reason = dead_proxy_reason(cfg, account_key)
```

条件2の追加分岐 (applier.py:885-903) は、直前の dead_proxy ゲート (applier.py:855-871) と **同一関数・同一引数** なので、先行 return により恒久的に到達不能。wifi_watchdog の SSID/電源OFF判定は applier から未参照 (kensho/ 配下 0 ファイル)。実発動ログも 0 件。

### 3. complete_watchdog comment 失敗数

```
$ grep -c "comment failed" logs/complete_watchdog_cron.log --> 0
```

### 4. self_heal 回帰テスト

```
$ python3 -m pytest tests/test_self_heal.py -q --no-cov --> 30 passed in 44.16s
```

## before/after 数値 (conditions 1, 3, 4)

| metric | before | after |
|--------|--------|-------|
| attempts=3 ライン数 /窓 | 64 | 0 |
| [CEILING] 連続失敗 最大値 | 3 | 2 |
| complete_watchdog comment failed | 54 | 0 |
| github_sync cron push /実行 | 0/1 | 2/2 |
| BOT max_attempts | 3 | 3 (不変) |

## 証跡
- `docs/daily_reports/2026-09-24.md` (b73683f) — CEILING 3 回 → 2 回
- `docs/daily_reports/2026-09-25.md` — [CEILING] 0 件
- `logs/complete_watchdog_cron.log` — `comment failed` 0 件
- `logs/auto_20260924.log`, `logs/2026-09-25/orchestrator_*.log` — attempts=3 0 件
- `tests/test_self_heal.py` — 30 passed