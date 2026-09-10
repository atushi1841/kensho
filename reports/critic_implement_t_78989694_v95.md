# t_78989694 実装報告 — Gumroad X analytics 日次収集の恒久化 (v95)

## verification_evidence

task: t_78989694

### 1. 収集実行（9/11 06:37-06:41 JST、ラッパー直接実行・全7件live完走）

$ tail -8 /mnt/d/Project2/kensho/logs/gumroad_x_analytics.log
2026-09-05 | views=46 | fav=0 | conv=0
2026-09-06 | views=47 | fav=0 | conv=0
2026-09-07 | views=61 | fav=0 | conv=0
2026-09-08 | views=29 | fav=0 | conv=0
2026-09-09 | views=43 | fav=0 | conv=0
2026-09-10 | views=28 | fav=0 | conv=0
2026-09-11 | views=1 | fav=0 | conv=0
保存: /mnt/d/Project2/kensho/data/gumroad_x_analytics.json

（9/11 views=1 は当日投稿直後の実値。fav/conv=0は抽選未確定の正常値。直前run 06:36は curl(28) タイムアウトで views=None 混在→Noneガードが既存良好値を維持、run5で完走）

### 2. native crontab（08:45投稿→08:50収集→10:00判定窓）

$ crontab -l | grep gumroad_x
45 8 * * * /home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/gumroad_x_post.sh > /dev/null 2>&1
50 8 * * * /home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/gumroad_x_xanalytics.sh > /dev/null 2>&1

旧 one-shot `0 9 7 9 *`（v26-2 t_3556cdc6）はコメント化して廃止明示済み。WSL cronデーモン稼働中（pgrep -x cron → 304, 2953470）。Hermes cron不使用の理由: kensho-revenue-worker は gateway 非起動プロファイルで silent-forever（memory既知）→ gumroad_x_post.sh と同型の .sh+crontab パターン。

### 3. コミット（push済み）

$ git log --oneline -2
b258267 docs(reports): v95実装報告 t_78989694 (evidence durability)
f48f33b fix(collect): v95 Gumroad X analytics収集を日次永続化+views_latest Noneガード (t_78989694)

$ git status --porcelain -uno

（空=追跡ファイルの未コミット変更なし）

### 4. 受け入れ条件実測（critic v95）

$ python3 -c "import json;d=json.load(open('/mnt/d/Project2/kensho/data/gumroad_x_analytics.json'));print(len(d), max(v.get('views_latest',0) for v in d.values()))"
7 61

→ entries=7、views_latest最大=61（閾値>42を通過、null混入なし）。データmtime age=1252s < 86400s（本日収集済み）。views_latest内訳: 09-05=46, 09-06=47, 09-07=61, 09-08=29, 09-09=43, 09-10=28, 09-11=1。

### 5. 変更物一覧

| 物 | 種別 |
|---|---|
| scripts/gumroad_x_xanalytics.py | 修正（views_latest Noneガード、commit f48f33b） |
| ~/.hermes/profiles/kensho-revenue-worker/scripts/gumroad_x_xanalytics.sh | 新規ラッパー（D:マウント待ち300s、log追記） |
| native crontab | one-shot `0 9 7 9 *` 廃止 → `50 8 * * *` 日次 |
| data/gumroad_x_analytics.json | 9/11スナップショット追記済み（views_latest=1） |
