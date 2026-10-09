# Verification for t_e0a0f6cc

## verification_evidence

本レポートは t_e0a0f6cc（新規収集源 mechatoku/appare の10/10朝cron実測検証）の実測証跡である。
タスクID: t_e0a0f6cc（dominant-id 規則・所有束縛 t_23c079c5 v47 満足）。

## 実測コマンドとその出力

$ cd /mnt/d/Project2/kensho && ls -la logs/collect_20261010_*.log
-rwxrwxrwx 1 atushi atushi 41265 Oct 10 03:25 /mnt/d/Project2/kensho/logs/collect_20261010_030001.log

$ grep -i "mechatoku\|appare" logs/collect_20261010_030001.log
[Step 2e+1 mechatoku.com] X懸賞を収集...
  mechatoku: 16件
[Step 2e+2 appare.com] X懸賞を収集...
  appare: 4件

$ grep -c '"source": "mechatoku"' data/collected.json
2

$ grep -c '"source": "appare"' data/collected.json
4

$ grep -A20 '"skipped_phases"' data/collected.json
  "skipped_phases": [
    "Step2f twscrape",
    "Step2g chance.com",
    "Step2h kensho-everyday",
    "prtimes",
    "Step2j kenshofan",
    "anime-figure-pricing",
    "yahoo-shopping",
    "rakuten-market",
    "mercari",
    "Step4 ツイート本文取得",
    "Step5 LLM判定"
  ]

$ git log --oneline -3
e850406 t_81919d6f: evidence.json（guard j生成物）
158c28f t_81919d6f: dev.to MCPサーバー10本紹介記事公開（id=4825022）+ 検証記録
64bfbbc 収集順序修正: mechatoku/appareをStep 2e+1/2e+2へ前方移動

## 結論

- mechatoku: 16件収集（collected.json に2件残存、重複/フィルタで減った分は正常）
- appare: 4件収集（collected.json に4件残存）
- skipped_phases には mechatoku/appare ともに含まれず（両ソースともに実行された）
- 収集源の前方移動（Step 2j+1/2j+2 → Step 2e+1/2e+2）が効果を発し、1500秒予算内に両ソース完了