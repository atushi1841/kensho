# critic v143 実装レポート — audit_bot_safety.py 検査6「日跨ぎ規則性」追加 (t_32c2723a)
日付: 2026-09-13 (JST) / ワーカー: kensho-revenue-worker / run 448

## 変更内容

- `scripts/audit_bot_safety.py`:
  - 定数: `REGULARITY_WINDOW_DAYS=7`, `REGULARITY_MIN_DAYS=3`,
    `REGULARITY_START_STDEV_MIN=30`, `REGULARITY_COUNT_CV=0.15`（カード本文指定の閾値を定数化）
  - `_regularity_signals(date_s)` 追加: 直近7日（対象日含）のアカウント別
    「初動時刻(分)の標準偏差(pstdev, JST)」「日次件数のCV(pstdev/mean)」を算出し、
    `stdev<30 OR CV<0.15` を `[正規性]` シグナルとして出力。
    初動・件数とも全監査行（status不問）ベース。日数3未満・ファイル欠損・不正日付・
    不正JSON行は例外なく無視（統計不能=判定しない=偽陽性ガード）。
  - `main()` の検査5直後に `problems.extend(...)` で組み込み。`--state` 既報抑制・
    「出力=要確認/空=安全」cron monitor契約はそのまま維持（シグナル文字列は date_s を
    含むため当日内は同一文字列=既報扱いで重複出力なし）。
- `tests/test_audit_bot_safety_regularity.py`: 8テスト（OR条件2方向・偽陽性ガード・
  日数不足・窓7日境界・不正行無視・ファイル欠損・不正日付）。

## スコープ遵守（オペレーター補足 9/13 16:2x JST）

- 応募ロジック・`config.yaml` の `batch_jitter_minutes`（303行目, 値15）は一切変更せず。
  本変更は読み取り専用監査の可視化のみ。
- 検出垢 (atushi16 / zin20120731) への実ジッタ改修（窓拡幅等）は行わず、シグナル文言内
  に「別カードでGO提案」と明示。

## 検証結果

- `python3 scripts/audit_bot_safety.py 2026-09-12` → 終了コード1、`[正規性]` 2件:
  atushi16 初動stdev13.9分・件数CV0.10 / zin20120731 初動stdev17.3分 — 監査前実測
  （research-20260913.md・criticレポート表）と一致。
- 回帰ゼロ: 従来5検査出力は HEAD版と同一（2026-08-27 で差分ゼロ確認、正規性行を
  除いた全出力一致）。
- 検証コマンド: `python3 scripts/audit_bot_safety.py 2026-09-12 | grep -c 正規性` → 2 (≥1 OK)
- `python3 -m pytest -q` → 568 passed, 5 skipped（新8テスト含む、回帰なし）
- mypy: 新規コード起因エラーゼロ（既存4件のみ、HEAD版と同じ4件）
## 失敗時代替案

（30日で誤検知週2回超→単体スクリプト格下げ）: 未発動。9/13 --today 実走で検出2件=
想定内（実データのパターン自体が規則的）、誤検知兆候なし。

## verification_evidence

対象タスク: t_32c2723a（スコープ=監査可視化のみ、パイプライン非改修）

```
$ cd /mnt/d/Project2/kensho && python3 scripts/audit_bot_safety.py 2026-09-12 | grep -c 正規性
2
```

```
$ cd /mnt/d/Project2/kensho && python3 scripts/audit_bot_safety.py 2026-09-12; echo exit=$?
[audit_bot_safety] 2026-09-12: 2件のBOTシグナル検出
  [正規性] 2026-09-12 atushi16 初動stdev13.9分(<30)・件数CV0.10(<0.15) (直近7日 初動8時台中心・件数mean104 → 規則的パターン=検出リスク、batch時刻ジッタ改修は別カードでGO提案)
  [正規性] 2026-09-12 zin20120731 初動stdev17.3分(<30) (直近7日 初動8時台中心・件数mean97 → 規則的パターン=検出リスク、batch時刻ジッタ改修は別カードでGO提案)
exit=1
```

```
$ cd /mnt/d/Project2/kensho && python3 -m pytest -q 2>&1 | tail -1
================== 568 passed, 5 skipped in 76.49s (0:01:16) ===================
```

- 回帰ゼロ確認: HEAD版(従来5検査)と新出力を 2026-08-27 / 2026-09-12 で突合、正規性行を
  除く全出力一致（2026-08-27 は両者 exit 0・同一1行）。
- mypy: 新規起因エラー0（HEAD版と同じ既存4件のみ）。
- 実測一致: 初動stdev atushi16=13.9分 / zin20120731=17.3分、件数 CV=0.10 / 0.23、
  mean=104 / 97 — research-20260913.md・critic提案表（t_32c2723a カード本文）と一致。
