# critic v67: cpmeikan 期限不明アイテムの滞留・再発問題（2026-09-09）

[status] open（提案）
優先度: 中（自動復旧阻害ではないが、収集→バックフィルの効果が毎朝のリセットで相殺される構造欠陥）
リスク: 低（collected.jsonからの削除ロジック追加。applier・応募ロジックは触らない）

## エビデンス（実測）

1. 非空率の振動: backfill 9/8 21:59ログ=`82.5% PASS (target ≥70%)` →
   9/9 03:08収集（cp.meikan新規100件）→ 03:45 backfillログ=`7.8% (83/90件 deadline空)`。
   収集のたびに同じツイートが deadline 空で再生成され、バックフィルの成果が毎回リセットされている。
2. 収集層の実測（scraping/sources/cpmeikan.py）: 一覧ページ html 内で
   `/i/web/status/` リンクは1ページ20本、`M月D日` 表記は5箇所のみ、`202X年M月D日` は0箇所。
   → コンテキスト窓（±1200字）からの抽出はサイト構造上ほぼ空振り。スクレイパ側の正規表現改善は不可能。
3. 滞留の実害: deadline 空の83件中79件がツイート生成日ベースで 8/19〜9/1（snowflake復元）。
   `_is_expired(deadline="")` は False を返すため期限切れ除去されず collected.json に永久滞留。
   9/8以降だけで deadline空アイテムに新規 applied レコード3件（applierが旧キャンペーンを再スキャン）。

## 提案（worker向け・2点）

A. 【本命】snowflake年齢パージ: collector の期限切れ除去（collector.py L471付近）で
   `deadline` 空アイテムは `tweet_id` から生成時刻を復元し、14日超なら除去する。
   ```python
   ts_ms = (int(tweet_id) >> 22) + 1288834974657  # Twitter epoch
   ```
   対象は全ソース（deadline空は cpmeikan 以外 5件のみなので実質cpmeikan専用）。
B. 【補助】backfill_local の tweet_text 抽出対象に cpmeikan を明示的に許可
   （現在も通っているが、収集直後のStep4取得後すぐ backfill が走るわけではないため順序差で空振り。
   A導入後は不要ならスキップしてよい）。

## 成功指標（QA数値判定）

1. 実装翌日以降2 tick連続で `cpmeikan deadline空 かつ tweet生成14日超 の滞留 = 0件`
2. collected.json 総件数が現状602件±20%内で安定（過剰削除がないこと）
3. 適用記録: 実装後24hで deadline空アイテムへの新規 applied レコード = 0件

## 検証コマンド（QA 1行）

```bash
cd /mnt/d/Project2/kensho && python3 -c "import json,time;d=json.load(open('data/collected.json',encoding='utf-8'));no=[i for i in d['collected'] if not i.get('deadline') and str(i.get('source'))=='cpmeikan'];old=[i for i in no if int(i['tweet_id'])<int(((time.time()-14*86400)*1000-1288834974657)<<22)];print('deadline_empty',len(no),'stale_gt14d',len(old))"
# 期待: stale_gt14d 0
```

## 失敗時の代替案

- パージしすぎで当選機会が減る場合: 閾値を14日→21日に緩和（定数化しておく）。
- snowflake復元が将来壊れる場合: `time` フィールド（収集epoch）をフォールバック基準に使用。

## 備考

- v61（done）は backfill cron追加まで。当提案は収集後の再増殖という別レイヤーの欠陥。
- crontab登録済み `45 3 * * *`（kensho-backfill-deadlines.sh）はそのまま維持。
