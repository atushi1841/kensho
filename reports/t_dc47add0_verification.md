## verification_evidence
$ python3 scripts/actor_weekly_run.py --force --skip-x-post --max 1
[2026-10-09 14:54:16] Apify API token: apif...[REDACTED]dWMA
[2026-10-09 14:54:20] 対象アクター: 5件
[2026-10-09 14:54:20] 対象アクター: 1件 / 週=2026-W41 / slot=a
[2026-10-09 14:54:20]   [1] mercari-japan-search-scraper → whSePszWpMtfeLYBp
[2026-10-09 14:54:20] 実行[1/1]: mercari-japan-search-scraper...
[2026-10-09 14:54:21]   status=None run_id=None error=HTTP 400
[2026-10-09 14:54:21] X投稿をスキップ (--skip-x-post)
[2026-10-09 14:54:21] dev.to 投稿成功: https://dev.to/atu_ino_ed473db24d76d234a/apify-actor-weekly-run-mercari-japan-search-scraper-unknown-7bg
[2026-10-09 14:54:21] 状態記録: /mnt/d/Project2/kensho/data/actor_weekly_run_state.json
[2026-10-09 14:54:21] 完了: 2026-W41/a に 1 件実行・投稿
$ cat data/actor_weekly_run_state.json
{
  "posted_weeks": {
    "2026-W41": {
      "a": {
        "whSePszWpMtfeLYBp": {
          "run_id": null,
          "status": null,
          "dataset_id": null,
          "error": "HTTP 400",
          "tweet_id": "",
          "devto_url": "https://dev.to/atu_ino_ed473db24d76d234a/apify-actor-weekly-run-mercari-japan-search-scraper-unknown-7bg",
          "posted_at": "2026-10-09T14:54:21+00:00",
          "date": "2026-10-09",
          "slot": "a"
        }
      }
    }
  }
}
$ ls -la scripts/actor_weekly_run.py
-rwxrwxrwx 1 atushi atushi 18483 Oct  9 14:55 scripts/actor_weekly_run.py
