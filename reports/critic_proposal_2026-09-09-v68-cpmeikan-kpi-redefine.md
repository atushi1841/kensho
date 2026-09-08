# critic v68: cpmeikan deadline KPI再定義 - stale-empty=0ハードゲート化、70%目標を撤去 (2026-09-09)

[status] open(提案) / 優先度: 中 / リスク: 低(監視ロジックのみ。収集・応募ロジックは触らない)

## エビデンス(実測 2026-09-09 06:20)

1. v67パージ(t_b1bb39d0)は実装・QA完了済み: commit c126bbd、QA 5点PASS(pytest 490、sim 602->545)。
   ただし発動は次回収集時からで、現物はまだ stale 57件滞留中(streak待ち)。
2. collected.json実測: total=602 / cpmeikan=90 / deadline空=83 / うちsnowflake 14日超=57 /
   若年空(7-13日)=26。
3. パージ後cpmeikan非空率 = 7/33 = 21.2%。
   現行CHECK閾値「非空率 >= 70%」(backfill_deadlines)は構造的に到達不能。
   理由: cp.meikan一覧ページに期限表記が存在しない(9/9 v67実測: M月D日表記は1ページ5箇所のみ、
   deadline空は毎収集で再生成される)。
4. tweet_text期限抽出での救済上限も小さい: 若年空26件中 date mention(数字+月+数字+日)は4件のみ。
   全件抽出成功でも 11/33 = 33.3% で70%に届かない。
   (= QA v67 handoff「KPI再定義かtweet_text抽出提案か」の結論: 抽出では足りない)

## 提案

A. backfill_deadlines のCHECKを2層KPIに変更:
   - L1 ハードゲート(FAILライン): deadline空 かつ tweet生成14日超 = 0件
     (v67パージの成功指標そのもの。1件でも出たらバグ再発としてFAIL)
   - L2 監視ライン(情報表示のみ): cpmeikan非空率 20%以上(実測帯21-30%)。
     未達でもCHECK FAIL行は出さない。日次誤FAIL=alert fatigueの恒久解消。
B. (任意・低優先) tweet_textに date mentionのある4件の期限抽出。
   現行backfill_localのキーワード条件を緩める必要があり、効果は4件だけなのでA導入後は見送りで可。

## 成功指標(数値)

- 9/10 03:45以降のbackfillログに「target >=70% ... CHECK」FAIL行が 0本。
- L1表示 stale_empty = 0(収集2 tick連続)。

## 検証コマンド

python3 -c "import json,time; d=json.load(open('data/collected.json')); now=time.time(); e=[x for x in d['collected'] if not x.get('deadline') and x.get('source')=='cpmeikan']; s=[x for x in e if (now-(((int(str(x.get('tweet_id') or '0'))>>22)+1288834974657)/1000))>1209600]; print('stale_empty=',len(s))"
# -> パージ発動後は 0。FAILライン確認: grep -c 'target' $(ls -t logs/backfill_deadlines_*.log | head -1)

## 失敗時の代替案

CHECKロジック再構築が重ければ、閾値を70%->25%へ引き下げ+ FAILをWARN表記に変えるだけの変更で可。
いずれにせよ70%固定は撤去すること(構造的到達不能な目標は毎日止まらない誤警報になる)。

## 参考

- v67詳細: reports/critic_proposal_2026-09-09-v67-cpmeikan-stale-purge.md
- QA検証: reports/daily-improvement-2026-09-09-qa-v67.md
