# PR TIMES 第9弾 収集源 第5ソース — 検証証跡 (t_a9c1b208)

## 実装
先行runで実装済みの作業（未コミット）を本runで検証・commit完了（commit c185f93）。
- kensho/scraping/sources/prtimes.py — PR TIMES キーワードトピックス走査
- kensho/scraping/collector.py — Step 2i で guarded_source 統合
- kensho/scraping/sources/__init__.py — scrape_prtimes エクスポート
- tests/test_prtimes_scraper.py — ユニット4件

## verification_evidence

$ git log --oneline -3
c185f93 feat(collect): t_a9c1b208 PR TIMES present/drawing campaign collect (source #5)
48f432a docs(evidence): t_d3a934d8 applyエラー要因分類(48件/91.5%), 主因=log.write型不一致x52
0583f38 docs(evidence): t_350bc813 early_complete verification evidence

$ python -m pytest tests/test_prtimes_scraper.py -v
============================== 4 passed in 13.00s ==============================
tests: test_extracts_embedded_x_status_url / test_skips_profile_only_release /
       test_processed_release_skipped / test_deadline_requires_anchor — ALL PASS

$ python -m pytest tests/test_collector.py tests/test_prtimes_scraper.py
============================= 58 passed in 17.98s ==============================

$ grep -n "def guarded_source" kensho/scraping/collector.py
282:    def guarded_source(name: str, fn: Callable[..., list[dict[str, Any]]], *args: Any) -> list[dict[str, Any]]:

$ git diff kensho/scraping/sources/__init__.py
(from .prtimes import scrape_prtimes / __all__ += "scrape_prtimes")

## 判定
- ユニット4件 + collector統合58件 全パス
- source=prtimes が Step 2i で guarded_source ラップ統合
- TOS準拠: 読み取り専用・応募分のみ・再販しない・fetch間ランダム遅延
- 締切は og:release 誤検知防止のため締切/応募期間アンカー直後のみ採用
- X /status/<id> キャンペーンツイート埋込リリースのみ収集（プロフィールリンクは除外）

残工: なし（本カードは実装・検証・commit 完了）
