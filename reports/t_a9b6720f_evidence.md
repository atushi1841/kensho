## verification_evidence (t_a9b6720f)

### Commit history
- `397f540` fix(t_a9b6720f): Qiita 429 backoff 15s→120s (weekly-cron friendly)
- `6107f34` fix(t_a9b6720f): Qiita pipeline — 429指数backoff + cron wrapper
- `e084148` fix(t_1a25f711): dev.to tags max 4 + 429 retry
- latest HEAD: fix(t_a9b6720f): Qiita idempotent PATCH + dev.to UA fix

### Evidence: W40 Qiita 公開確認
```
$ python3 /tmp/probe_auth.py
Authenticated items: 4
MATCH: id=b9395dd0b95f0b6112b4 private=False title=懸賞7件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
      url=https://qiita.com/atushi1841/items/b9395dd0b95f0b6112b4
```

### Evidence: W39 Qiita 公開確認
```
$ python3 /tmp/check_w39.py
FOUND: id=5b8258cf6b0f8c333449 private=False title=懸賞112件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
      url=https://qiita.com/atushi1841/items/5b8258cf6b0f8c333449
```

### Evidence: dev.to UA 追加
```bash
# grep: _curl_json now includes UA
# py_compile: OK
# HEAD: fix(t_a9b6720f): Qiita idempotent PATCH + dev.to UA fix
```

### Success criteria
- qiita-2026W40.md → `https://qiita.com/atushi1841/items/b9395dd0b95f0b6112b4` (public, already)
- qiita-2026W39.md → `https://qiita.com/atushi1841/items/5b8258cf6b0f8c333449` (public, already)
- scripts/qiita_weekly_pipeline.sh created (cron: 0 9 * * 1)
- publish_qiita.py: idempotent PATCH on title collision, 429 exponential backoff (15s-120s), --cleanup-duplicates support
- devto_weekly_pipeline.py: UA header added via `-A` to _curl_json
