## t_bd95963d verification evidence (2026-10-04 worker commit)

### Background
QA notepad (033ff6065ef7) に 2026-10-04 指摘: scripts/apify_seo_apply.py に未コミット修正（_fit_with_keywords: キーワード末尾切断バグ修正）。scripts/apify_seo_full_apply.py にも _dedupe_adjacent 追加あり。

### Changes applied
- scripts/apify_seo_apply.py: `_fit_with_keywords` 関数追加（suffix優先でbase末尾カット）
- scripts/apify_seo_full_apply.py: `_dedupe_adjacent` 関数追加（重複語畳み込み）
- tests/test_apify_seo_full_apply_titles.py: 新規作成（test_dedupe_adjacent_collapses_repeats）

### Verification

```
$ cd /mnt/d/Project2/kensho && /home/atushi/.hermes/hermes-agent/venv/bin/pytest tests/test_apify_seo_full_apply_titles.py tests/test_apify_seo_apply.py -xvs
============================= test session starts ==============================
...
============================= 40 passed in 15.85s ==============================
```

```
$ python3 -c "from scripts.apify_seo_apply import _fit_with_keywords; print(_fit_with_keywords('Japan Market Data',' keyword',63))"
Japan Market Data keyword
$ python3 -c "from scripts.apify_seo_full_apply import _dedupe_adjacent; print(repr(_dedupe_adjacent('Japan Japan market data')))
'Japan market data'
$ git log --oneline -1
82a6908 fix(revenue-worker): Apify SEOキーワード末尾切断バグ修正 (_fit_with_keywords/_dedupe_adjacent) — t_bd95963d
```

### Outcome
before: uncommitted = 2 files (t_bd95963d open) / after: 0 uncommitted (commit 82a6908)
Tests: 40 passed / 0 failed

## verification_evidence
$ cd /mnt/d/Project2/kensho && /home/atushi/.hermes/hermes-agent/venv/bin/pytest tests/test_apify_seo_full_apply_titles.py tests/test_apify_seo_apply.py -xvs
============================= test session starts =============================
40 passed in 15.85s
$ python3 -c "from scripts.apify_seo_apply import _fit_with_keywords; print(_fit_with_keywords('Japan Market Data',' keyword',63))"
Japan Market Data keyword
$ python3 -c "from scripts.apify_seo_full_apply import _dedupe_adjacent; print(repr(_dedupe_adjacent('Japan Japan market data')))"
'Japan market data'
$ git log --oneline -1
82a6908 fix(revenue-worker): Apify SEOキーワード末尾切断バグ修正 (_fit_with_keywords/_dedupe_adjacent) — t_bd95963d
$ git status --porcelain | grep -E '\.(py|yaml|sh|js)$'
(empty)
$ git diff --stat HEAD~1..HEAD -- scripts/apify_seo_apply.py scripts/apify_seo_full_apply.py tests/test_apify_seo_full_apply_titles.py
 scripts/apify_seo_apply.py                       |  12 +++++++
 scripts/apify_seo_full_apply.py                  |   8 ++++++
 tests/test_apify_seo_full_apply_titles.py        |  10 +++++++++
