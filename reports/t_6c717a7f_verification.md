# t_6c717a7f verification evidence

## verification_evidence

```
$ ls /mnt/d/Project2/apify-portfolio-stats.json
-rwxrwxrwx 1 atushi atushi 181352 Oct  4 04:56 /mnt/d/Project2/apify-portfolio-stats.json
```

```
$ jq 'length' /mnt/d/Project2/apify-portfolio-stats.json
30
```

```
$ grep -o '"external_users":[0-9]*' /mnt/d/Project2/apify-portfolio-stats.json | sort | uniq -c | head
     30 "external_users":0
```

```
$ grep -c 'external_runs' /mnt/d/Project2/kensho/data/revenue-daily.json
31
```

```
$ python3 scripts/revenue-health-check.py
[ALERT] external_runs=0 連続 31日 (100.0%) — 外部顧客なし継続
```

```
$ python3 scripts/apify_ppe_external_runner.py --dry-run
[SKIP] japan-used-camera-market-scraper: interval < 24h
[SKIP] japan-watch-market-scraper: interval < 24h
... (all skipped due to 24h interval)
```

```
$ ls /mnt/d/Project2/kensho/reports/journalism/drafts/
devto-2026W39.md  devto-2026W40.md  qiita-2026W39.md  qiita-2026W40.md
```

```
$ grep -i qiita /mnt/d/Project2/kensho/.env 2>&1
(no output — QIITA_TOKEN not configured)
```

## Root cause

33 days of external_users_total=0 despite:
- SEO batch applied 2026-09-04 (86 actors, description>=120 chars)
- dev.to 8 articles with Apify Store links
- Reddit warmup 2 comments (karma 1→4)
- GitHub 30 repos + 6 MCP READMEs
- Weekly Apify PPE external runner (0 external runs)

Root cause: **internal owner-run bleed** — ALL runs on Apify actors are owner-initiated (userId=VMz6nlpHoGIjTeSXS). No external user has ever triggered any actor run. Apify Store search CTR is near-zero for Japanese dataset keywords.

## Blocked channels (require USER ACTION)

1. **Qiita**: draft qiita-2026W40.md exists at reports/journalism/drafts/ but requires QIITA_TOKEN in .env (currently absent). User must add token and manually publish.
2. **Zenn**: no API — requires git push to Zenn-linked GitHub repo (none found under @atushi16).
3. **note.com**: API returned 404, likely needs OAuth flow.

## Success metric status

- Target: external_users_total >= 1 (30-day measure)
- Current: external_users_total = 0 (day 33)
- Direction: UP (all promotion channels exhausted, no new actionable channel without credentials)

## Alternative considered

note.com and AtCoder contest participation (per task body) — both require user-side setup (OAuth credentials, account registration).