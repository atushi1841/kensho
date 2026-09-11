# critic v135 実装レポート: loop_health v92 park時刻dedup窓の再導入 — t_8fed223a

日付: 2026-09-12 / ワーカー: kensho-revenue-worker / 出典カード: t_8fed223a（QA run411）
対象: `scripts/loop_health.sh`（repo正本）→ `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh`（cron実体）へmd5一致コピー。

## 退行の事実（カード根拠どおり）

- v133系（a1a85db/9423ac6/b5f5cd9）の `scripts/loop_health.sh` に `is_time_dedup`/`DEDUP_OK` 出現0回 = v92 (7327ab7) の時刻dedupがリライト時に丸ごと消失していた。
- park gateは `PARK_COOLDOWN_S`(6h) のみで、30分スパンの再実行で target が切り替わると別targetを連続parkしうる（v92真因＝自動復旧阻害の再発経路）。

## 実装（v133c）

1. `PARK_DEDUP_WINDOW_S`（既定1800s、env上書き可）を追加。
2. stateへ `last_park_ts` / `last_park_result` / `last_park_target` を永続化（読み込み+単一最終書き込み、v133の「全フィールド保持して書く」原則準拠）。
3. park gate先頭で窓判定:
   - 直近試行が `parked`/`already_scheduled` なら **target切替を問わず** dedup（別target連続park遮断＝v92真因の直接対策）。
   - `dry_run_would_park`/`schedule_failed`/`skipped_status_*` は同一target限定でdedup。
   - `dedup_skip` は窓をスライドしない（last_park_* を更新しない）— v92 counted_tick 設計と同じ方向。
4. 試行系（dry_run/already_scheduled/park成否/skipped_status）は全て窓前進。
5. 失敗時代替案（cooldown 6h化）は不要 — 窓dedup単体で成功指標を満たす。

## 成功指標の実測（カード記載: 同一escalation状態で2回連続実行→2回目がdedup系、last_park_target不変）

| 指標 | 期待値 | 実測 |
|---|---|---|
| T1 連続2実行（dry-run窓） | 2回目 dedup系・target不変 | dry_run_would_park → dedup_skip / t_fake12345 不変 DEDUP_OK |
| T2 窓経過後（31分前へ巻戻し） | 再試行される | dry_run_would_park WINDOW_SLIDE_OK |
| T3 parked窓+別target切替 | dedup_skip・target不変 | dedup_skip / t_other11111 不変 CROSS_TARGET_BLOCK_OK |
| T4 窓外・実在しないtarget | 試行され窓前進 | skipped_status_unknown WINDOW_ADVANCE_OK |
| T5 healthy board | park_action=none 無変更 | none HEALTHY_NOOP_OK |
| 本番連続2実行 | park_action一致・board無変更 | none / none（score=100、comment/schedule発行なし） |

## verification_evidence

$ bash -n /mnt/d/Project2/kensho/scripts/loop_health.sh && echo SYNTAX_OK
SYNTAX_OK

$ bash /tmp/v133c_acceptance.sh
T1 DEDUP_OK (dry_run_would_park / dedup_skip / t_fake12345)
T2 WINDOW_SLIDE_OK (dry_run_would_park)
T3 CROSS_TARGET_BLOCK_OK (dedup_skip / t_other11111)
T4 WINDOW_ADVANCE_OK (skipped_status_unknown)
T5 HEALTHY_NOOP_OK

$ bash scripts/loop_health.sh >/tmp/h1.json; bash scripts/loop_health.sh >/tmp/h2.json; jq -r .park_action /tmp/h1.json /tmp/h2.json
none
none

$ md5sum /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh /mnt/d/Project2/kensho/scripts/loop_health.sh
c9f81f035e990c9767f540af646d24a0  /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
c9f81f035e990c9767f540af646d24a0  /mnt/d/Project2/kensho/scripts/loop_health.sh

$ grep -c "DEDUP_OK\|PARK_DEDUP_WINDOW_S" /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
8

## QAへの申し送り

- 受入テストは偽task（t_fake12345）+ 隔離state（/tmp/v133c_state.json）+ 存在しないboard名で実施、実boardへcomment/schedule一切なし。ロールバック=本コミットのrevert（profileコピーも同一コミットで戻る）。
- 実運用の窓前進は park試行時のみ。monitor周期が30分未満でも dedup_skip は窓を伸ばさないため、実park間隔の下限は cooldown(6h) のまま不変。
- 窓値変更が必要な場合は `PARK_DEDUP_WINDOW_S`（env or L54）のみ触ること（v92申し送りと同じ制約）。
