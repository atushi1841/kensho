# t_cfe11a7c — Gumroad CDP collect timeout fix: verification evidence

Task: pre-check CDP + auto-launch + split timeouts + last_success_at + freshness label.
Critic v60 proposal: reports/critic_proposal_2026-09-08-v60-gumroad-timeout-fix.md

## Root cause (empirically re-confirmed during implementation)

1. `echo > /dev/tcp/127.0.0.1/9333` from WSL is ALWAYS unresolved (Connection refused)
   even while Windows Chrome listens on Windows 127.0.0.1:9333. WSL and Windows have
   separate network stacks here — the Python(WSL)-side port check can never correctly
   judge CDP availability. (Checked: WSL `curl http://127.0.0.1:9334/json` -> HTTP=000
   while Windows node.exe reached the same port and collected Gumroad successfully.)
2. Launching Chrome with the FIXED profile `C:\temp\gumroad-cdp9333` handoffs to an
   existing instance (Chrome message: "このブラウザ・セッションで開かれています") and
   the CDP port is NOT opened → node's 3x8s launch wait exceeded the old 90s subprocess
   timeout => TimeoutExpired => last-value freeze.

## Fix implemented

- scripts/gumroad_sales_collect.js (Windows-side, where CDP is actually reachable):
  - ensureChrome() = pre-check + auto-launch + wait (≤45s), IPv4+IPv6 tolerant.
  - Unique user-data-dir per run (defeats stale-profile handoff), --headless=new.
  - Browser.close + unique profile cleanup after collect.
  - persists last_success_at in the state file.
- scripts/kensho_revenue_collect.py:
  - update_gumroad_state_via_cdp() runs node ONCE with GUMROAD_TOTAL_TIMEOUT=240s
    (was 90s), print timeout-mark/fail-mark on failure, persist last_success_at on success.
  - Drops the unreliable WSL-side port check (documented why).
- scripts/kensho_revenue_dashboard.py: Gumroad card shows "売上データ更新: N時間前",
  ⚠️ red when >24h.
- data/gumroad_state.json seeded/updated with last_success_at.
- tests/test_revenue_collect.py: +TestGumroadCdpResilience (9 cases).

## verification_evidence

$ cd /mnt/d/Project2/kensho && "/mnt/c/Program Files/nodejs/node.exe" --check "D:\\Project2\\kensho\\scripts\\gumroad_sales_collect.js" && echo "JS SYNTAX OK"
=> JS SYNTAX OK

$ python3 -m pytest tests/test_revenue_collect.py -q --no-cov
=> 30 passed in 1.05s

$ python3 -m pytest -q --no-cov
=> 469 passed, 5 skipped in 40.85s

$ timeout 300 python3 scripts/kensho_revenue_collect.py 2>&1 | grep -cE 'timeout-mark|fail-mark'
=> 0   (run 1)
=> 0   (run 2, consecutive)
=> 0   (run 3, consecutive)   — 3 consecutive collect runs, 0 timeout/fail marks

$ python3 -c "...last_success_at..."   (read from data/gumroad_state.json)
=> last_success_at = "2026-09-08T19:22:29.703"   (collected just now, within 24h)
=> login_ok = true, sales_page_ok = true

$ python3 scripts/kensho_revenue_dashboard.py && grep -o "売上データ更新[^<]*" revenue-status.html
=> ✓ revenue-status.html 生成完了; "売上データ更新: 0時間前"

## Acceptance criteria met
- 3 consecutive collect runs with 0 timeout-mark/fail-mark: MET.
- last_success_at within 24h: MET (19:22 today).
- Freshness label shown in report: MET.

## Out of scope / notes
- No Gumroad API credential exists in .env/config (CDP remains the collection path).
- Generated data files (revenue-daily.json, revenue-status.html, gumroad_state.json)
  were refreshed by the successful runs and are part of this commit.
