## verification_evidence

$ git -C /mnt/d/Project2/kensho log --oneline -3
2ea7842 t_2be0e7aa: add twscrape_success_rate tests
06f606e t_4067980d: add verification report
50095b7 t_4067980d: knshow 502 origin_outage 即breakでリトライ短縮 + referer 仮説破棄コメント

$ git -C /mnt/d/Project2/kensho show --name-only -s 1d5318a
kensho/scraping/source_health.py

$ git -C /mnt/d/Project2/kensho show --name-only -s dba4e0c
kensho/scraping/collector.py
kensho/scraping/source_health.py

$ python3 -m pytest tests/test_source_health.py -q
tests/test_source_health.py ...................                          [100%]
============================== 19 passed in 14.55s ==============================

$ grep -n 'twscrape_success_rate' kensho/scraping/source_health.py
74:        if "twscrape_success_rate" not in self._state:
75:            self._state["twscrape_success_rate"] = {"runs": 0, "successes": 0, "last": 0.0}
107:            # t_2be0e7aa: twscrape_success_rate は日付ロールでも保持（累積成功率）
108:            twscrape_metric = self._state.get("twscrape_success_rate", {"runs": 0, "successes": 0, "last": 0.0})
109:            self._state = {"date": self._date(), "sources": {}, "last_roll": self._state.get("date"), "twscrape_success_rate": twscrape_metric}
158:        meta = self._state.setdefault("twscrape_success_rate", {"runs": 0, "successes": 0, "last": 0.0})

$ grep -n 'record_twscrape_run' kensho/scraping/collector.py
743:            health.record_twscrape_run(len(twscrape_items) > 0)

$ git -C /mnt/d/Project2/kensho log --oneline -1 dba4e0c
dba4e0c t_2be0e7aa: twscrape 連続失敗スキップ + source_health twscrape_success_rate

$ cat data/source_health.json | python3 -m json.tool | head -20
{
  "date": "2026-09-25",
  "sources": {
    "knshow": {
      "attempts": 4,
      "failures": 4,
      "consecutive_failures": 4,
      "skipped": 8,
      "last_error": "http=502(origin_outage)",
      "last_failure": "2026-09-25T11:02:29"
    },
