# t_2419836e verification report — critic v170: 検知層の「0成功行を完了扱い」バグ修正

- 種別: 応募パイプライン検知層（loop_health business KPI gate / kensho-apply-stall-check.sh）の「0成功完了行を完了扱い」するバグ修正
- 日付: 2026-09-17 (JST)
- 対象タスク: t_2419836e（critic v170）
- 制約: 応募ロジック/応募パイプラインの挙動は一切変更しない（検知判定の修正のみ）。実際、本修正で変更したのは以下の正規表現 / grep 判定のみで、応募・収集コードは無変更。

## 背景（実測RCA）

応募パイプライン停止が2日目に入っても loop_health は score=100/business_ok=true のまま「稼働中」を誤表示。原因は2箇所とも「完了行の判定」から 0成功 が除外されていないこと:

1. profile 版 loop_health.sh:260 — `_re.search(r"完了:\s*\d+成功", _line)` が `完了: 0成功/0エラー`（停止時に毎15分書き込まれる行）にもマッチ → done_count が0にならず `done_count==0` の停止判定が発動しない。
2. kensho-apply-stall-check.sh — `grep -c '完了'` / `grep '完了'` が 0成功行も完了扱い → stall なし＝稼働中SILENT とマスク。

## 修正内容

- 正規表現を全対象で `完了:\s*[1-9][0-9]*成功`（成功数>=1 の行のみ完了扱い）に限定。
  - profile loop_health.sh の business KPI gate 集計 (`完了:\s*[1-9][0-9]*成功`)
  - kensho-apply-stall-check.sh: `COMPLETE_RE='完了:[[:space:]]*[1-9][0-9]*成功'` を定義し、当日 count / 履歴走査 / 当日最新行の3箇所の `grep` をすべて `grep -E "$COMPLETE_RE"` に変更。
  - 同一スクリプトの repo (scripts/) と profile (kensho-sweeps/scripts/) の両方に反映。

## 検証

### 成功指標（数値）再現

停止中(0成功ログ) → score<=60 かつ business_ok=false かつ alert='WARN: apply stopped'
復旧後(成功>0の完了行1件あり) → score>=80

### 実行証跡（--dry-run --no-park、`--tasks '[]'` でビジネスゲートを単体検証。ボード/スケジュール副作用なし）

```console
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh --tasks '[]' --board kensho-ai-team --state ... --dry-run --no-park   # LOOPHEALTH_LOG_PATH=0成功のみのログ, LOOPHEALTH_JST_HOUR=14
RESULT score=60 business_ok=False business_done=0 alert=WARN: apply stopped
```
→ 停止中: score=60 (<=60) / business_ok=False / alert='WARN: apply stopped' ✓

```console
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh --tasks '[]' --board kensho-ai-team --state ... --dry-run --no-park   # LOOPHEALTH_LOG_PATH=実ログ(完了: 15成功/0エラー), LOOPHEALTH_JST_HOUR=14
RESULT score=100 business_ok=True business_done=2 alert=OK
```
→ 復旧後: score=100 (>=80) / business_ok=True ✓

```console
$ grep -cE '完了:[[:space:]]*[1-9][0-9]*成功' /mnt/d/Project2/kensho/logs/auto_20260917.log
2
$ grep -nE '完了:[[:space:]]*[0-9]+成功' /mnt/d/Project2/kensho/logs/auto_20260917.log
595:2026-09-17 07:55:14.443 | INFO | ...   完了: 0成功/0エラー（0秒）
1136:[OK] 完了: 15成功 / 0エラー
1141:2026-09-17 08:33:03.921 | INFO | ...   完了: 15成功/0エラー（1447秒）
```
→ 実ログには 0成功 の停滞行(595)と、成功>0 の完了行(1136/1141=同一08:33バッチ)が混在。修正後は 0成功行(595)が集計から除外され、業務バッチ(15成功)のみ完了扱いされることを上記 STOP/RECOVERY 両結果で確認。補足: 本RC実測時点で08:33に15成功バッチが走行していたため、現在は「復旧後」分岐が現役（停止が score100 にマスクされない＝修正が機能）。

### kensho-apply-stall-check.sh（repo 版と profile 版の両方で同じ挙動を確認）

```console
$ KENSO_STALL_HOUR=14 KENSO_STALL_PROJECT_DIR=<0成功のみのlogs> bash scripts/kensho-apply-stall-check.sh --dry-run
NOTIFY-STAGE: stall=121min >= 120min
[Kensho] 応募停止検知: 121分「完了」行なし (今日0件, src=(recent 40d logs に完了履歴なし))
```
→ 0成功のみのログは完了扱いしない（今日0件）→ 停止を検知して通知 ✓

```console
$ KENSO_STALL_HOUR=14 KENSO_STALL_PROJECT_DIR=<15成功を含むlogs> bash scripts/kensho-apply-stall-check.sh --dry-run
SILENT: 稼働中 (stall=7min, 完了=1)
```
→ 成功>0 の完了行がある場合は稼働中SILENT（従来どおり）✓

### 退行テスト

tests/test_loop_health_business.py に v170 検知を固定するテストを2本追加（計5本）。

```console
$ LOOP_HEALTH_SCRIPT=/home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh python -m pytest tests/test_loop_health_business.py -q
5 passed, 1 warning in 23.60s
```
- test_apply_stopped_zero_success_lines_not_completion —「0成功のみのログ」で business_done==0 / business_ok=False / score<=60 を固定（v170バグの再発防止）
- test_apply_recovered_success_gt0_restores_ok — 成功>0 の完了行1件で business_ok=True / score>=80 へ復旧

## 変更ファイル

- /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh（デプロイ版の business KPI gate 正規表現）
- /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-apply-stall-check.sh（デプロイ版）
- scripts/kensho-apply-stall-check.sh（repo 版）
- tests/test_loop_health_business.py（v170 検知テスト2本追加）

## 残作業

なし。検知層のみの修正で、応募ロジック/パイプライン挙動は無変更。

## verification_evidence

実行実証の生出力（上記セクションの `$ cmd` に対応する実際のツール出力を逐次収録）。

```console
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh ...（STOP, LOOPHEALTH_LOG_PATH=0成功のみ, JST=14）
RESULT score=60 business_ok=False business_done=0 alert=WARN: apply stopped

$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh ...（RECOVERY, 実ログ, JST=14）
RESULT score=100 business_ok=True business_done=2 alert=OK

$ grep -cE '完了:[[:space:]]*[1-9][0-9]*成功' /mnt/d/Project2/kensho/logs/auto_20260917.log
2

$ KENSO_STALL_HOUR=14 ... bash scripts/kensho-apply-stall-check.sh --dry-run （<0成功のみのlogs>）
NOTIFY-STAGE: stall=121min >= 120min
[Kensho] 応募停止検知: 121分「完了」行なし (今日0件, src=(recent 40d logs に完了履歴なし))

$ KENSO_STALL_HOUR=14 ... bash scripts/kensho-apply-stall-check.sh --dry-run （<15成功のlogs>）
SILENT: 稼働中 (stall=7min, 完了=1)

$ LOOP_HEALTH_SCRIPT=... python -m pytest tests/test_loop_health_business.py -q
5 passed, 1 warning in 23.60s
```

t_2419836e の完了判定（critic v170 acceptance）は全て確認済み。
