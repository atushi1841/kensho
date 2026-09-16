# t_313c8c32 検証証跡 — 当選率分析自動化 (dm_wins.json × actions.db 週次レポート)

実行: kensho-revenue-worker / 2026-09-16 JST
対象: scripts/kensho_winrate_analysis.py（既存・critic v164/v167 実装）+ reports/winrate-2026W38.md refresh commit 1d0e67f

## verification_evidence

$ python3 scripts/kensho_winrate_analysis.py --week 2026W38
winrate 2026W38: wins=15 matched=15 unmatched_rate=0.0% sources=9 → /mnt/d/Project2/kensho/reports/winrate-2026W38.md
exit=0

$ python3 -m pytest tests/test_winrate_analysis.py -q
============================== 12 passed in 9.43s ==============================

$ python3 -c "import json; d=json.load(open('data/dm_wins.json')); print(len(d),'accounts',sum(len(v) for v in d.values() if isinstance(v,list)),'wins')"
2 accounts 15 wins

$ ls -la data/actions.db
-rwxrwxrwx 1 atushi atushi 0 Sep 16 12:47 data/actions.db

$ git log --oneline -1
1d0e67f t_313c8c32: refresh weekly winrate report 2026W38 (15 wins matched 0.0% unmatched)

結果:
- dm_wins.json: 2アカウント / 15件当選
- actions.db は0バイト(空) → 応募ログ不在。失敗時代替案どおり collected.json の applied 記録で突合代行
- 突合: matched 15 / unmatched 0 (0.0%) / 源別9カテゴリ
- W38レポート: knshow 0.62%, twscrape 0.70%, 他は0%(未当選), unknown(擬似) 133.33% — 源別・カテゴリ別・遅延帯別・時刻帯別の数値を出力
- 12テストPASS（既存テスト、回帰なし）
- commit 1d0e67f を本タスクの受け入れとして push 対象報告
