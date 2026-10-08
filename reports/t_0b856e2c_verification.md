# t_0b856e2c 検証レポート

## 実装内容
- dev.to W45 記事公開（id=4817031）+ タイトル修正（PUT 200）
- RapidAPI 非公開4API公開化は 2026-09-18 ユーザー方針「RapidAPI見送り」により放棄

## verification_evidence

$ curl -s -H "Authorization: Bearer $(grep DEVTO_API_KEY /mnt/d/Project2/kensho/.env | cut -d'=' -f2)" "https://dev.to/api/articles/4817031" | jq -r '.title'
Apify Actorsで日本市場データを無料でスクレイピング8選（2026年版）

$ curl -s -H "Authorization: Bearer $(grep DEVTO_API_KEY /mnt/d/Project2/kensho/.env | cut -d'=' -f2)" "https://dev.to/api/articles/4817031" | jq -r '.url'
https://dev.to/atu_ino_ed473db24d76d234a/untitled-437f

$ find /mnt/d/Project2/kensho -name "rapidapi_auth.json" 2>/dev/null | wc -l
0

$ git -C /mnt/d/Project2/kensho log --oneline -3
0d1987e (HEAD -> main) t_0b856e2c: dev.to W45 article + verification report
12b7199 t_0b856e2c: dev.to W45 article title fix
8415790 t_0b856e2c: dev.to weekly pipeline dry-run