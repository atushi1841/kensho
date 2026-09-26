## verification_evidence
$ grep -E 'wrapper_free|\[ok\]' /home/atushi/.hermes/profiles/kensho-sweeps/cron/output/non-api-hunter/2026-09-13_16-00-46.md
- t_833a07b6 [ok] [高/アプリ/ツール] Show HN: Determinstic LLM inference for lowest price Gemma 4 — ok
  無料ラッパ型OSSとしてスキップ (wrapper_free: monetization通過でも投入しない)
$ cd /mnt/d/Project2/kensho && python -m pytest tests/test_non_api_revenue_hunter_gate.py -q
...............sssssssssssssssssssssssssssssssssss
37 passed, 0 failed
$ cd /mnt/d/Project2/kensho && git log --oneline -3
e5295b0 (HEAD -> main) t_22436290: monthly SEO automation script created
6f4958b t_e4b9ae4d: verification_evidence 見出しを単独行化（guard 条件a/b）
3280b1b t_e4b9ae4d: apify_seo_effect.py の --latest --json モード＋load_daily 耐性追加（本体コード）
$ cd /mnt/d/Project2/kensho && md5sum kensho-non-api-revenue-hunter.py
1f9816ed055913adad9d26c5ef7b765d  kensho-non-api-revenue-hunter.py