# t_926e8b9f kenshofan.com 第5収集源 所有権化 — 検証証跡

## objective
QA notepad 2026-09-22 指摘の未コミット kensho/scraping/sources/kenshofan.py を破棄せず所有権化して
コミットし、guard(d) 未コミット抵触による全 worker の done 汚染と軌道維持不能を解消する。

## 変更
- `kensho/scraping/sources/kenshofan.py`（新規）: 懸賞ファン一覧（最大20ページ）から X URL を直接収集。
  deadline/winner_count 周辺テキスト抽出、dict.fromkeys 順序維持一意化、has_skip_keyword。
- `kensho/scraping/collector.py`: Step 2j に scrape_kenshofan を配線。
- `kensho/scraping/source_health.py`: PRIMARY_SOURCES に "kenshofan" 追加。
- `kensho/scraping/sources/__init__.py`: scrape_kenshofan を export（__all__ 追加）。

## verification_evidence
`git status --short | grep -E '\.py' | grep -v '^??'` → 出力行なし（scraping系コードの未コミット0件） (t_926e8b9f)
`/home/atushi/kensho-venv/bin/python import_check.py` → `scrape_kenshofan_in_dir = True`（import/export確認） (t_926e8b9f)
`/home/atushi/kensho-venv/bin/python live_run_kenshofan.py` → `RESULT items=24 elapsed=31.8s` / `RESULT connect_timeout_lines=0`（実測kenshofan_items=24>0, ConnectTimeout=0<3） (t_926e8b9f)
`git show -s --format=%H HEAD` → `31b514cf96a6a6dd3f51e3867a465729e94ee86e`（所有権コミット） (t_926e8b9f)
`pytest -x -q` → `1 failed, 479 passed, 4 skipped in 114.65s`（唯一のfailは tests/test_loop_health.py::test_no_running_top_task_none — jqツール欠落の環境要因・scraping/kenshofanと無関係の既知fail。kenshofan関連テストは全pass） (t_926e8b9f)
`git status --short` → scraping系.py の M/A row 0件（コミット後クリーン） (t_926e8b9f)

## 備考
- kenshofan.com は単一ページレイアウト（/page/2 が HTTP 404）。コードは非200で正常終了し 24件 収集。検証OK。
- コミットは push 済み。references/reports 成果物は git 追跡し guard(g) 準拠。
