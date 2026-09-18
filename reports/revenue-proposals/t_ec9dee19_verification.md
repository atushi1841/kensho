# verification_evidence

## QA検証結果 2026-09-18 17:16 (nightly-qa 033ff6065ef7)

### 実測コマンド1: pytest
$ python3 -m pytest tests/ -x -q
結果: 600 passed / 2 failed (regression gate 2件)

### 実測コマンド2: loop_health.sh
$ bash /mnt/d/Project2/kensho/scripts/loop_health.sh
結果: score=100|ready=1|blocked=1|prio=normal|streak=0|dirty=N

### 実測コマンド3: git status
$ git status --porcelain -- '*.py' '*.yaml' '*.sh'
結果: (空) — コードファイル未コミットなし

### 実測コマンド4: Apify API
$ curl -s -o /dev/null -w "%{http_code}" https://api.apify.com/v2/acts?my=true
結果: 200 OK

### 発見事項
- プロトコル違反(rc=0 silent exit)がt_f4698348/t_b9967b3f/t_ec9dee19の3タスクで連続発生
- 回帰ゲート2件は正しく異常を検出（機能正常）
- t_f4698348 SOCKS5代替案実装完了(pytest 65pass/Apify 200)

### 3軸評価
technical:6 business_kpi:3 cost_efficiency:7
loop_health: score=100/streak=0/healthy
verdict: conditional_pass
