# verification report for t_4067980d

generated: 2026-09-26T10:55:00+09:00  (by kanban_done_guard.py --write-report)
workdir: /mnt/d/Project2/kensho

## verification_evidence

本レポートは t_4067980d 実装の検証証跡です。
タスクID: t_4067980d（dominant-id 条件・所有束縛 t_23c079c5 v47 満足）

# コミット存在確認
$ git -C /mnt/d/Project2/kensho log --oneline -1
50095b7 t_4067980d: knshow 502 origin_outage 即breakでリトライ短縮 + referer 仮説破棄コメント

# origin_outage 即break実装確認
$ grep -n "CF_ORIGIN_OUTAGE" /mnt/d/Project2/kensho/kensho/scraping/sources/knshow.py
147:if code >= 500 and classify_knshow_failure(code, html) == CF_ORIGIN_OUTAGE:

# テスト結果
$ python3 -m pytest /mnt/d/Project2/kensho/tests/test_knshow_retry.py -q
tests/test_knshow_retry.py ............ 12 passed

$ python3 -m pytest /mnt/d/Project2/kensho/tests/test_knshow_cloudflare.py -q
tests/test_knshow_cloudflare.py .......................... 26 passed
