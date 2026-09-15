# t_865a35e3 監査証跡 — 型間アクション開始の同時刻集中度 read-only 監査

成果物: reports/jitter-audit-2026-09.md（本ファイルは検証証跡）。
対象: logs/2026-09-13..15 orchestratorログ359ファイル / セッション開始171件。
応募ロジック改修なし（read-only制約遵守）。判定: 1分バケット複数垢同時開始=14/142(9.9%)、最大3垢、秒一致0件。真の指紋は15分グリッド±2分への98.8%集中。対策実装は別カードでGO確認を仰ぐ。

## verification_evidence

$ cd /mnt/d/Project2/kensho/logs && grep -hE "\[Kensho\].*開始$" 2026-09-1*/orchestrator_*.log | wc -l
171

$ cd /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_865a35e3 && python3 stats2.py
N=171 starts, buckets=142, multi-acct buckets=14 (9.9%), starts-in-multi=29 (17.0%)
cross-file(並列ワーカー衝突)=9, starts=19
offsets from 15min grid: [(0, 10), (1, 96), (2, 63), (3, 1), (4, 1)]
CROSS 2026-09-13 19:01 {'TankanNotes': ['orchestrator_190009.log'], 'atushi16': ['orchestrator_190009.log'], 'kudou_aoshi': ['orchestrator_190010.log']}

$ cd /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_865a35e3 && python3 stats.py
total=171 within±2min of 15-min grid: 169 (98.8%)
2026-09-13: starts=38 buckets=28 multi2+=6 (21.4%) max=3
2026-09-14: starts=72 buckets=62 multi2+=1 (1.6%) max=2
2026-09-15: starts=61 buckets=52 multi2+=7 (13.5%) max=2
gaps n=168 p10=19 p25=45 median=855 p75=913
gaps<=60s=49 (29.2%)  <=30s=32  <=10s=4

$ cd /mnt/d/Project2/kensho && ls reports/jitter-audit-*.md && grep -c '同時' reports/jitter-audit-2026-09.md
reports/jitter-audit-2026-09.md
8

$ grep -hoE "▶ \S+（時刻[0-9:]{5}" 2026-09-1*/orchestrator_*.log | sed -E 's/.*時刻([0-9]{2}):([0-9]{2})/\1 \2/' | awk '{m=$2%15; d=(m>7)?15-m:m; if(d<=2)c0++} END{print c0}'
85

$ grep -n "batch_jitter_minutes" /mnt/d/Project2/kensho/config.yaml
281:  batch_jitter_minutes: 15      # バッチ時刻を±15分ランダム化（BOT対策）
