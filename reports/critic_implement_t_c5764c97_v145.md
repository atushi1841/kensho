# critic v145 実装報告 — kensho-revenue-report.sh プレースホルダ教訓書き込みの構造バグ自己修復

- task: **t_c5764c97**
- 対象ファイル: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-revenue-report.sh`
- バックアップ: `kensho-revenue-report.sh.bak-v145`

## 概要

critic cron (job 4baf143523e0, nightly-critic) が実行する `scripts/kensho-revenue-report.sh` が、
従来 step4/5/7 で毎回無条件に `lessons` キーを上書きし、step7 で「今日の分析完了。次回への申し送り：なし」に固定 → 実測値・申し送りが critic 起動ごとに消滅していた。これを観察ベースの追記運用へ改修した。

## 変更内容

1. step4/5 の無条件 `set lessons` を削除（上書きによる教訓消滅を根絶）。
2. step3 観察セクションで前日実測値を収集ログから算出・`reports/critic-observe-YYYY-MM-DD.md` に保存:
   - 前日 KENKAKU 平均取得件数（`collect_YYYYMMDD_*.log` の「計N件」平均）
   - 前日 ConnectTimeout 行数（同ログの行数）
   - 前日 apply 成功率（`auto_YYYYMMDD.log` の「完了: N成功/Mエラー」集計）
3. step7 の lessons 書き込みを「日付: 前日実測サマリ1行」の追記へ変更。既存教訓を保持しつつ最大5行にローリング（重複日付は新しい1行のみ残す）。プレースホルダ語（検証中／例として／申し送り：なし）は一切書き込まない。
4. `$HOME` 依存を `SELF_DIR` 絶対パス固定（loop_health.sh / kensho-kanban-sync.sh の解決を安定化）。応募ロジック・config・パイプラインには未接触。

## verification_evidence

動作確認 : .sh (bash) / 手動実行

```
$ cd /tmp && bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-revenue-report.sh > /tmp/critic_v145_run2.log 2>&1; echo "EXIT=$?"
EXIT=0
```

```
$ hermes cron notepad 4baf143523e0 get lessons 2>/dev/null | grep -E '[0-9]+(件|%|行)' | wc -l
2
```

```
$ hermes cron notepad 4baf143523e0 get lessons 2>/dev/null | grep -E '[0-9]+(件|%|行)' | head -1
2026-09-14: KENKAKU平均 10.4件 / ConnectTimeout 47件 / apply成功率 91.2%
```

```
$ hermes cron notepad 4baf143523e0 get lessons 2>/dev/null | grep -cE '検証中|例として|申し送り：なし'
0
```

```
$ cat /mnt/d/Project2/kensho/reports/critic-observe-2026-09-15.md
# Critic観察レポート 2026-09-15
対象: 前日 2026-09-14
- KENKAKU平均取得: 10.4件（14セッション）
- ConnectTimeout: 47件/day
- apply成功率: 91.2%（成功540/エラー52）
```

第1回試行でも step8 kensho-kanban-sync が `$HOME` 相対のため解決できず「コマンド not found」となったため、SELF_DIR を絶対パス固定して再実行し EXIT=0・全step成功を確認。
