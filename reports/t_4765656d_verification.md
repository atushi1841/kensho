# t_4765656d Verification Report — Apify PPE 5 Actors SEO Gap

## Date: 2026-09-28
## Task: README.md source fix + Custom icon (pictureUrl) for 5 Apify actors

---

## 1. README.md Status (sourceFiles / GitHub)

| Actor | ID | sourceType | README chars | Status |
|---|---|---|---|---|
| ai-model-price-api | 6EvRs5kF1mbelC03M | SOURCE_FILES | 828 | ✅ OK |
| japan-anime-figure-price-data | DKzufUSvmuXNKHeYx | SOURCE_FILES | 3678 | ✅ OK (pre-existing) |
| japan-jma-weather | 1g84gsOT7vE9yxNla | SOURCE_FILES | 2355 | ✅ OK (pre-existing) |
| japan-mhlw-medical | 62DcoLUAkkOB1hGAH | SOURCE_FILES | 857 | ✅ OK |
| japan-prize-giveaway-scraper | FPlcw4CWMAKooZNe6 | GIT_REPO | 2153 (GitHub) | ✅ OK |

**Result: All 5 actors have README.md in source. No gaps remain.**

## 2. Custom Icon (pictureUrl)

All 5 actors: **pictureUrl = None**

**Finding: pictureUrl is NOT writable via Apify REST API.**
- Confirmed by `apify_batch_updater.py` lines 71-77: PUT /v2/acts/{id} has no pictureUrl field
- Even a valid PNG URL returns HTTP 400 `invalid-picture-url`
- Custom icons are Console-UI only (cannot be automated)

**Verdict: Blocked by Apify API. Not a code defect.**

## 3. SEO Fields (seoTitle / seoDescription)

| Actor | seoTitle | seoDescription |
|---|---|---|
| ai-model-price-api | None | None |
| japan-anime-figure-price-data | None | None |
| japan-jma-weather | "Japan Weather Scraper — JMA Forecasts & Alerts" | "Japan Meteorological Agency weather scraper..." |
| japan-mhlw-medical | None | None |
| japan-prize-giveaway-scraper | None | None |

## 4. Conclusion

- README: **All 5 actors verified OK** — no further action needed
- Icon (pictureUrl): **API-blocked** — cannot be automated; Apify Console manual upload required
- SEO fields: Out of scope for this task