# nightly-qa run4 検証レポート（2026-09-25 06:12-06:45）

## 0. 結論
- **【高】稼働垢 kudou(50件/日) が本日08:00から応募停止する状態を発見 → 実測特定・恒久修正・push 済み。**
  真因は run3 とは別: `data/account_wifi_map.json` の**静的対応(adapter/port)が消えた破損マップ**を
  一時スクリプト `test_fix.py` が本番パスに書き込んでいたこと。破損後は `proxy_state="停止"`（実際はLISTEN）
  が毎tick書き込まれ、`network_outage_reason()` が kudou を「圏外」と誤判定していた。
- ループ健康度は **score=100 / streak=0 / alert=OK**（実測・下記）。run2/run3の parse_error・過並列警告は解消。
- 要ユーザー対応は**なし**（すべてチーム内で解決）。

## verification_evidence

### 1. 破損の実測（修正前）
```
$ python3 -c "import json;d=json.load(open('data/account_wifi_map.json'));print(sorted(d['accounts'][0].keys()),len(d['accounts']))"
['adapter_state', 'display', 'egress_ip', 'egress_ok', 'egress_warn_home', 'key', 'proxy_state'] 3
$ git show HEAD:data/account_wifi_map.json | python3 -c "..."
kudou adapter=kudou_RM10JE_B port=1082 transport=POVOスマホHS | 接続 listen 106.146.21.233 True False
$ git diff --stat data/account_wifi_map.json
 1 file changed, 12 insertions(+), 79 deletions(-)
$ timeout 12 curl -s --socks5-hostname 172.26.80.1:1082 https://api.ipify.org
106.146.21.233        # ← プロキシは生きている
$ powershell.exe -NoProfile -Command "Get-NetTCPConnection -State Listen | ?{$_.LocalPort -ge 1080 -and $_.LocalPort -le 1090} | %{$_.LocalPort}"
1085 / 1082 / 1081    # ← LISTEN している
$ python3 -c "from kensho.utils.safety import network_outage_reason ..."
'kudou' -> "ネットワーク出区: アカウント 'kudou' のWiFiが未検出状態"   # ← 稼働垢が圏外扱い（08:00から応募スキップ）
```
書き込み元の特定: 破損マップは live 項目だけの最小JSON（`key/display/adapter_state/proxy_state` +
refresh が足す `egress_*`）で、垢の並び順が `test_fix.py` の疑似データと一致。同スクリプトは
`data_dir = "/mnt/d/Project2/kensho/data"` に直接書き込む実装だった（本番データ破壊）。

### 2. 修正（即時復旧）
```
$ git show HEAD:data/account_wifi_map.json > data/account_wifi_map.json
$ python3 scripts/refresh_wifi_map.py
[ok] account_wifi_map.json 更新 (6 fields, ports=[1081, 1082, 1085])
$ python3 -c "...network_outage_reason..."
'kudou' -> ''                    # 復旧
'atushi16' -> '' / 'TankanNotes' -> ''
'zin20120731' -> "ネットワーク出区: ... 切断状態"   # 正当（バッチ停止垢）
'toushiwatch' -> "ネットワーク出区: ... 切断状態"   # 正当
```

### 3. 恒久対策（再発防止）
- `scripts/refresh_wifi_map.py`: **静的対応(adapter/port)が欠落した map は書き込まず exit 2**（既存値保持）。
  破損マップを掻き回しスクリプトが上書きしても、偽の「停止」が以降の全tickに定着しない。
- `test_fix.py`: 本番 `data/` への書き込みを一時領域（`tempfile.mkdtemp`）へ隔離。
- `tests/test_refresh_wifi_map.py`: 破損契約テストを追加（破損mapを書き換えないことを固定）。
```
$ python3 -m pytest tests/test_refresh_wifi_map.py tests/test_loop_health.py -q
8 passed in 34.69s
$ H1=$(sha256sum data/account_wifi_map.json|cut -d' ' -f1); python3 test_fix.py >/dev/null; H2=$(sha256sum ...)
before=89c3a17357f5964027b2c8558ac6bdd0d427fd6d1a9ccb3b5806ae9aafb5716c
after =89c3a17357f5964027b2c8558ac6bdd0d427fd6d1a9ccb3b5806ae9aafb5716c  -> OK: 本番mapは不変
```

### 4. 本番経路での効果確認（15分cron）
```
$ python3 -c "import json;d=json.load(open('data/account_wifi_map.json'));print(d['updated_at'],d['measurement_ok'],[(a['key'],a['adapter_state'],a['proxy_state']) for a in d['accounts']])"
2026-09-25T06:20:25+09:00 True [('atushi16','有線(NIC)','listen'),('kudou','接続','listen'),('zin20120731','切断','停止'),('TankanNotes','有線(NIC)','listen'),('toushiwatch','切断','停止')]
```

### 5. ループ健康度（実測）
```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['score'],d['streak'],d['running'],d['blocked'],d['alert'],d['escalation'],d['business_ok'])"
100 0 4 6 OK False True
$ sqlite3 kanban.db "select status,count(*) from tasks group by status"
triage 0 / todo 2 / ready 0 / running 4 / blocked 6 / done 650
```
- 初回 05:2x の score=60/streak=2 は `running=8 > max_in_progress=4` の過並列減点で、故障ではない（設計どおり）。

### 6. 稼働KPI
```
$ grep -c 成立 logs/auto_20260925.log   -> 0     （08:00前・正常）
$ grep -c 成立 logs/auto_20260924.log   -> 870
$ tail logs/auto_20260925.log -> 06:09 正常終了 / 垢別起動: kudou / 処理待ちのバッチなし
```

### 7. 出口IP分離（ライブ実測）
```
$ for p in 1081 1082 1084 1085 1087; do curl -s --socks5-hostname 172.26.80.1:$p https://api.ipify.org; done
1081=219.104.132.236（自宅・atushi16のみ許可）/ 1082=106.146.21.233 / 1085=126.245.20.32
1084・1087=不通（バッチ停止垢・正当）   self_home_warn なし（違反0）
```

## 申し送り（次回以降）
1. **【中・要対応】`tests/test_loop_health_json_contract.py` が SyntaxError（L468: try に except なし）で
   `pytest` 全体が collection error になる**（untracked・作成元 = t_47a5b3fe）。全workerの自己レビュー
   `pytest -x -q` が自分の変更と無関係に赤くなるため、同カードを unblock して仕上げさせる。
   HEALTH_DEGRADED 明示も未実装（`grep -c HEALTH_DEGRADED scripts/loop_health.sh` -> 0）。
2. t_9f14ee5d（並列度 config 基準 + streak リセット）は実装が HEAD に存在し実測で効果確認
   （score=100 / running=4 で減点0）→ QA検証で done 化し、子 t_de7d7e84 のデッドロックを解消。
3. `test_fix.py` は untracked のまま（リポジトリに取り込まない）。今後も同種の「一時検証スクリプトが
   本番データを書く」事故を防ぐため、`data/` 直下への書き込みは一時領域経由を原則とする。
4. 日中窓(09-23)の再測必須: `has no attribute 'write'` / `multi_response accounts>=2=0/497`。

## 3軸評価
```json
{"evaluation":{"technical":{"score":8,"assessment":"破損マップ→圏外誤判定の因果を実測で特定し、即時復旧＋恒久ガード＋回帰テストを1コミットで投入","evidence":"修正前 kudou='ネットワーク出区'・ports LISTEN確認済 → 修正後 '' / pytest 8 passed / 15分cron map(kudou 接続 listen)"},"business_kpi":{"score":8,"assessment":"修正しなければ本日08:00からkudou(50件/日)が丸ごと停止していた。稼働3垢の応募継続を確認","evidence":"9/24成立870行・9/25 0行(08:00前で正常)・06:09 orchestrator正常終了・出口IP分離OK"},"cost_efficiency":{"score":6,"assessment":"loop_health.sh を複数カードが奪い合う構図は継続（.bak/.mybackup/.v14x が5個残留）。t_47a5b3fe の未完テストが全workerのpytestを赤くする分の損失","evidence":"git status で loop_health.sh 系バックアップ5件 + untracked テスト3件"},"loop_health":{"score":100,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":true,"notes":"5観点を個別記録。delegate_taskはツールセット外のため単一パス（代替案どおり）"},"verdict":"pass","next_steps":["t_47a5b3fe を unblock（SyntaxError解消＋HEALTH_DEGRADED実装）","t_9f14ee5d を done 化して t_de7d7e84 のデッドロック解消","09:00以降の応募ログで kudou の成立行を実測","loop_health.sh 系バックアップファイルの整理"]}
```
