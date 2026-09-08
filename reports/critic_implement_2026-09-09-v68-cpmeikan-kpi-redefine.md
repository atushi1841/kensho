# critic v68 実装報告 — cpmeikan KPI 再定義（CHECK 70% 廃止 + L1 stale_empty ハードゲート）

タスク: t_34decbc2 | 実装日: 2026-09-09 | commit: 934d61a

## 背景 / エビデンス
- 旧 KPI「cpmeikan deadline 非空率 ≥70%」は構造的に到達不能: 募集継続ツイートの期限が
  ページ本文に無く、抽出できるのは一覧から消えた後の期限切れツイートのみ。実測帯は 20-30%
  （v67 パージ後は残りが若年 item のみでさらに下がる）。毎朝 FAIL 行が出るが誰も直せない
  ＝アラート疲れの原因。
- 真に観測すべき失敗モードは「パージ不全で deadline 空・14日超が再溜まりする」こと
  （v67 で導入した collector パージの監視）。これをハードゲート化する。

## 実装
`backfill_deadlines.py`:
- 定数追加: `STALE_PURGE_DAYS = 14`（collector.py `_STALE_TWEET_DAYS` と連動、コメント明記）、
  `STALE_GATE_GRACE_DAYS = 1`。ゲート = 15日超。
  - 14日ちょうどでは FAIL しない: 収集は前夜〜21時、backfill は 03:45 で、正常 item でも
    パージ閾値を数時間〜半日超過して計測される（実測 14d18h 等が閾値内として通過）。
- ヘルパー `count_stale_empty(items, now, min_days)`:
  tweet_id（無ければ x_url 末尾）の snowflake から生成時刻を復元し、deadline 空 かつ
  年齢 > min_days 日の件数を返す。非数値 id / 取得不能は安全側（カウントしない）で None。
- 計測箇所は 1 つだけ: バックフィル適用前の生状態（main エントリ直後）。
  after 側で再計測すると age_freeze で deadline が埋まりパージ不全が秘匿されるため。
- L1 ハードゲート: `stale_empty(>15d) >= 1` → 明示 `FAIL` + `return code 1`（cron が拾う）。
  dry-run では FAIL 判定を出さず件数行のみ。>14d 純値は参考 INFO 併記。
- L2 監視ライン: cpmeikan 非空率を INFO 表示のみ（実測帯 20-30% の注記付き）。FAIL 行廃止。
- 旧 `CHECK 非空率 ≥70%` 行は完全削除 → 成功指標「9/10 03:45 以降 CHECK ゼロ」は構造保証。

`tests/test_deadline_backfill.py`: `TestCountStaleEmpty` 6 件追加
（recent 除外 / >gate カウント / 境界±1分 / deadline 有り除外 / 非数値 id / x_url フォールバック）。

## downstream 安全確認
`CHECK` / `≥70` 行をパースする消費者は scripts/・core/・crontab・Hermes cron に存在しない
（grep 確認済み）。出力フォーマット変更は自由。

## verification_evidence

（本タスク: t_34decbc2 / commit 934d61a）

$ python -m pytest tests/test_deadline_backfill.py -q
..................... [100%] → 21 passed

$ python -m pytest tests/ -q -p no:cacheprovider
→ 493 passed, 5 skipped, 1 failed（failure=patchright_import_test、stash して HEAD 版でも
  同一＝本タスク以前からの既存）

$ python -m ruff check backfill_deadlines.py tests/test_deadline_backfill.py && python -m ruff format --check backfill_deadlines.py tests/test_deadline_backfill.py
All checks passed! → 2 files already formatted

$ /home/atushi/kensho-venv/bin/python backfill_deadlines.py --dry-run
[L1] stale_empty( deadline空 かつ tweet年齢>15d ): 51 (>14d 純値 57) → dry-run（件数のみ）
[L2] cpmeikan deadline 非空率: 6.7% (INFO・実測帯20-30%) → EXIT=0、CHECK 行ゼロ

$ /home/atushi/kensho-venv/bin/python backfill_deadlines.py
残(若年・抽出不能): 51 → [L1] stale_empty(...>15d): 51 (>14d 純値 57) → FAIL → EXIT=1

$ /home/atushi/kensho-venv/bin/python /tmp/sim_postpurge_t34decbc2.py
sim: 602 → 545 items (purged 57) → [L1] stale_empty( deadline空 かつ tweet年齢>15d ): 0 (>14d 純値 0) → PASS → SCRIPT_EXIT=0

$ grep -n "CHECK\|target ≥70" backfill_deadlines.py
grep-rc=1（該当ゼロ＝CHECK 行完全除去を確認）

$ git show 934d61a --stat
2 files changed, 108 insertions(+), 6 deletions(-)

## 次ゲージ
- 9/9 09:45 backfill ログに [L1]/[L2] 行が出れば成功指標の前倒し確認可。
  ただし v67 パージは収集 tick 後に効くため、09:45 時点で L1=51 FAIL は想定内（収集未実行なら）。
- 完全解消の目安: 次回収集（〜21時）→ 9/10 03:45 で L1=0 PASS。
