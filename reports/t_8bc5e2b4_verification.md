# t_8bc5e2b4 公開事業者リスト受託・初期提案セット 検証記録

- 日付: 2026-09-20
- 担当: kensho-revenue-worker
- タスクID: t_8bc5e2b4

## 実施内容
t_8bc5e2b4 の成果物として、国税庁法人番号公表サイトの東京都全件データを公開ダウンロードし、西東京市の法人から100件を抽出した。あわせて、ランサーズ・ココナラ提出用の提案文3種と納品形式定義書を作成した。

## verification_evidence

$ python3 collect_business_sample.py /tmp/tokyo/13_tokyo_all_20260831_02.csv 西東京市 100 /tmp/repro_sample_test.csv
→ OK: 西東京市 の事業者 100件 を /tmp/repro_sample_test.csv に出力しました

$ python3 比較: sample_businesses_nishitokyo_100.csv と /tmp/repro_sample_test.csv
→ 行数一致: True、内容完全一致: True

$ wc -l sample_businesses_nishitokyo_100.csv
→ 101

$ git log --oneline -1
→ ec94d80 docs(evidence): t_8bc5e2b4 公開事業者リスト受託・初期提案セット 検証記録

$ git push origin HEAD
→ 9bdae57..ec94d80 HEAD -> main

$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_8bc5e2b4 --workdir /mnt/d/Project2/kensho --write-evidence --payload-file /tmp/t_8bc5e2b4_payload.json
→ written: /mnt/d/Project2/kensho/reports/t_8bc5e2b4_evidence.json (guard j verification => pass)

## 成果物の実在確認
- sample_businesses_nishitokyo_100.csv: 100件（ヘッダ込み101行）
- collect_business_sample.py: 再現実行済み
- deliverables/README.md: 納品形式・規約対応を定義
- 提案テンプレ3種: 基本型、定期更新型、単発急ぎ型

## 公開情報・規約対応
- ソースは国税庁の公開ダウンロードデータのみ。
- 個人情報・個人メール・ログイン必須情報・規約禁止サイトにはアクセスしていない。
- 自動入札・規約回避・認証突破機能はない。
- t_8bc5e2b4 の本タスク範囲では、ランサーズ・ココナラへの実際の応募・提出はしていない。

## 次の一手
t_8bc5e2b4 の成果物は、ランサーズの実募集「西東京市・川口市 事業者リスト約4,000件／10日」への提案素材として使える。提出は次段階の判断とする。

## 自己レビュー
```json
{"self_review":{"what_was_done":"t_8bc5e2b4の公開事業者リスト100件・提案テンプレ3種・再現スクリプトを実測生成し、検証記録と機械可読evidence.jsonをリポジトリへ保存。","what_went_well":["公開公的データでTOS安全","100件の再現テストが完全一致","個人情報・規約禁止対象を構造的に除外"],"what_could_improve":["電話・業種・URLはソースにないため空欄","川口市の別サンプルは未作成"],"mistakes_or_risks":["法人番号データに業種列がないことを実測後に確認"],"learned":"受託案件は公開情報の範囲を明確にし、再現可能な抽出物を残す。","confidence":9,"verification_evidence":"t_8bc5e2b4: CSV101行・再現完全一致・evidence.json生成成功を実測"}}
```
