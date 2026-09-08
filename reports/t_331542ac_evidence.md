# Evidence — t_331542ac (cpmeikan deadline欠損修复 + 期限切れSKIP発火検証)

Date: 2026-09-08 22:10 JST
Task: t_331542ac
Spec: reports/critic_proposal_2026-09-08-v61-cpmeikan-deadline-backfill.md

## 実行内容

1. Phase A — `backfill_deadlines.py`（v61改修版）を dry-run → 本実行で実施。
   冪等性確認のため2回実行（2回目 `Missing: 84 → 84 (fixed 0)` = 再処理なし）。
2. Phase B — `kensho/scraping/sources/cpmeikan.py` の締切抽出は fc377fd (2026-08-23)
   以降コミット済み（差分なし・作業済みとして確認）。収集時は本文周边1200字から
   `YYYY年M月D日` 等を抽出し `deadline` を埋めている。
3. 常設化 — `scripts/kensho-backfill-deadlines.sh` を新規作成（収集cron後45分に
   `/tmp/kensho-collect.lock` を flock -w 1800 で待ってからバックフィル実行）。
   crontab への登録は他プロセスの共有crontabのため本タスクでは行わず、
   次タスク（ops）に引き継ぎ。

## verification_evidence

ゲート(k): collected.json cpmeikan deadline非空率 ≥70%

```
$ cd /mnt/d/Project2/kensho && jq '.collected | map(select(.source=="cpmeikan")) | length' data/collected.json
480
$ jq '.collected | map(select(.source=="cpmeikan" and .deadline!="")) | length' data/collected.json
396
$ jq '.collected | length' data/collected.json
1064
```
→ 396/480 = 82.5% ≥ 70% PASS（修復前: 2/480）

ゲート(l): applier側の期限切れ除外が実際に発火しているログ1本以上

```
$ grep -r "期限切れ除外" logs/2026-09-08/
logs/2026-09-08/orchestrator_220016.log:[22:03:15] [索] 期限切れ除外: 225件
$ grep -B3 -A3 "期限切れ除外" logs/2026-09-08/orchestrator_220016.log
[22:03:14] [Kensho] この垢の未応募: 514件
[22:03:15] [索] 期限切れ除外: 225件
[22:03:15] [Kensho] 処理可能: 289件、目標: 16件（不足時は補充）
```
→ バックフィル後の22:00台応募セッションで225件が期限切れとして除外され、
   514件→289件に縮小。無駄アクション防止が実データで確認できた。

バックフィルラッパーの実行（end-to-end・冪等）:

```
$ bash scripts/kensho-backfill-deadlines.sh; echo "wrapper rc=$?"
wrapper rc=0
$ tail -6 logs/backfill_deadlines_$(date +%Y%m%d)_*.log（最新）
📊 Missing: 84 → 84 (fixed 0)
   cpmeikan deadline 非空率: 82.5% (target ≥70%)
[BACKUP] ✅ collected.json.20260908_215946.bak
[SAVE] ✅ collected.json保存完了 (1064件)
[21:59:46] backfill exit rc=0
```

## 所見・残課題

- 22:00収集のマージ（`_dedup_x_url_merge`: 空でないdeadline優先）で
  396件のdeadlineは持続。ただし `deadline_source` マーカーは収集側が
  再構築したエントリでは null に戻る（132件の age_freeze は持続、84件の
  local_extraction マーカーは消失）。deadline値自体は保持されるため
  機能影響なし。マーカー永続化は collector マージ側の課題として分離可。
- 残84件のcpmeikan deadline空欄は、サイト側リストに締切表記が無いもの
  （年齢90日超は age_freeze で2026-06-25等に凍結済み、以降は収集由来の
  生日期限）。coverage目標70%は超過済みで追加介入不要。
- `scripts/kensho-backfill-deadlines.sh` の crontab 登録（`45 3,9-21 * * *`）
  が未実施 → 後続opsタスクへ。
