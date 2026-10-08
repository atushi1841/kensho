# t_0b856e2c 検証レポート

## やったこと
1. loop_health確認: score=70, priority=new_proposals, blocked=0
2. t_0b856e2c claim（TTL 3600）
3. dev.to pipeline dry-run実行、未公開記事0件確認
4. dev.to W45記事を新規公開（title=Untitled）
5. PUT /articles/4817031でタイトル修正
6. rapidapi_auth.json確認→欠如
7. RapidAPI非公開4API公開化ブロック判定

## 検証コマンド
$ bash scripts/loop_health.sh | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['priority'],d['score'])"
new_proposals 70
$ hermes kanban claim t_0b856e2c --ttl 3600
Claimed t_0b856e2c
$ python3 /home/atushi/.hermes/profiles/kensho-sweeps/cache/scratch/fix_devto_4817031.py
PUT http: 200 / id: 4817031 / title: Apify Actorsで日本市場データを無料でスクレイピング8選（2026年版）

## 検証結果
- dev.to記事タイトル修正: 成功（PUT 200、GET title一致）
- RapidAPI公開化: 認証情報欠如でブロック（blocked）

## verification_evidence
t_0b856e2c
t_0b856e2c
t_0b856e2c

$ python3 fix_devto_4817031.py -> PUT http: 200 / GET title一致
$ cat rapidapi_auth.json -> cat: cannot access
$ git push -> 8415790..12b7199 main -> main
