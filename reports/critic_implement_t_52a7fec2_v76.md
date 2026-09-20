# knshow source_health統合 + 502追跡 (t_52a7fec2) — early_complete 報告

## 実施内容
PRIMARY_SOURCESに knshow 追加、collector Step1 一覧502を source_health へ追跡、連続>=4 で Telegram 通知・自動skip。commit 6e494f0 (t_52a7fec2) で実装済みのため早期完了。

## verification_evidence

$ git rev-parse HEAD
6e494f0e43e7a91b95dc2abdebc4accb2e3e4f3d

$ git log --oneline -3
6e494f0 fix: knshowをsource_health主要源に統合＋一覧502追跡・連続4回でTelegram通知 (t_52a7fec2)

$ python3 scripts/verify_knshow_health.py
VERIFY_OK: knshow 実在 + failures=4 + consecutive=4>=4 (alert条件を満たす)

$ python3 -m pytest tests/test_source_health.py -q
17 passed in 31.70s

$ grep -n "PRIMARY_SOURCES" kensho/scraping/source_health.py
47: PRIMARY_SOURCES: tuple[str, ...] = ("knshow", "ken-kaku", "kenshou.club", "cp.meikan", "ke-ma")
