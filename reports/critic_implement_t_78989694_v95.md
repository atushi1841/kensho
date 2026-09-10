# t_78989694 実装報告 — Gumroad X analytics 日次収集の恒久化 (v95)

## verification_evidence

task: t_78989694

### 1. 収集実行ログ（9/11 06:36-06:41 JST、ラッパー直接実行・完走）

$ tail -30 /mnt/d/Project2/kensho/logs/gumroad_x_analytics.log

最終ブロック（run5 06:37-06:41、全7件live取得成功・08:50収集相当の手動検証）:
```
2026-09-05 | views=46 | fav=0 | conv=0
2026-09-06 | views=47 | fav=0 | conv=0
2026-09-07 | views=61 | fav=0 | conv=0
2026-09-08 | views=29 | fav=0 | conv=0
2026-09-09 | views=43 | fav=0 | conv=0
2026-09-10 | views=28 | fav=0 | conv=0
2026-09-11 | views=1 | fav=0 | conv=0
保存: /mnt/d/Project2/kensho/data/gumroad_x_analytics.json
```
（9/11 views=1 は当日投稿直後の実値。fav/conv=0は当選発表前の正常値）
（run3 06:36はcurl(28)タイムアウトでviews_latest=null混在→ガードが既存値を維持、run4/run5で完走）

### 2. データ状態（data/gumroad_x_analytics.json 実測）

- entries=7（2026-09-05〜09-11、tweet_idキー）
- views_latest 全件数値: 46, 47, 61, 29, 43, 28, 1（null混入=0）
- Noneガードの実証: 9/6 entry は curl(28) タイムアウトsnapshot（21:31:58, views=null）が
  混在するが views_latest=47 を維持（ガード前のコードならnullで潰れていた）
- snapshots は回帰的に追記のみ（冪等性OK: 同一日に複数回実行しても重複許容・latest不変）

### 3. スケジュール（native crontab 実測）

$ crontab -l | grep -E "gumroad_x_(post|xanalytics)"

```
45 8 * * * /home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/gumroad_x_post.sh > /dev/null 2>&1
50 8 * * * /home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/gumroad_x_xanalytics.sh > /dev/null 2>&1
```

- 発火窓: 08:45投稿 → 08:50収集 → 10:00判定（critic v95制約）を厳守
- 旧 one-shot `0 9 7 9 *`（v26-2, t_3556cdc6）はコメント化して廃止明示
- WSL cronデーモン稼働中（pgrep -x cron = 304）
- Hermes cron不使用の理由: kensho-revenue-worker は gateway 非起動プロファイルで
  silent-forever（memory既知）→ gumroad_x_post.sh と同型の .sh+crontab パターン

### 4. コミット

$ git show --stat HEAD | tail -2

```
f48f33b fix(collect): v95 Gumroad X analytics収集を日次永続化+views_latest Noneガード (t_78989694)
 scripts/gumroad_x_xanalytics.py | 5 ++++-
```

### 5. 変更物一覧

| 物 | 種別 |
|---|---|
| scripts/gumroad_x_xanalytics.py | 修正（views_latest Noneガード、commit f48f33b） |
| ~/.hermes/profiles/kensho-revenue-worker/scripts/gumroad_x_xanalytics.sh | 新規ラッパー（D:マウント待ち300s、log追記） |
| native crontab | one-shot→50 8 * * * 日次 |
| data/gumroad_x_analytics.json | 9/11スナップショット追記済み（views_latest=1） |
