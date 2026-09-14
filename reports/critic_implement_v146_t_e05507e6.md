# critic v146 実装レポート — critic-observe へ源別ConnectTimeout分割追加 t_e05507e6

日付: 2026-09-15
対象スクリプト: /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-revenue-report.sh（プロファイル外・スクリプトのみ。応募ロジック・config・パイプライン・kenkaku.pyは未変更）

## 変更内容
1. step3観察部に源別集計を追加: ConnectTimeout行を `grep -h "ConnectTimeout" collect_YYYYMMDD_*.log` で取得し、`[KENKAKU]` `[KCLUB]` `[KEMA]` `[CPMK]` を夫々 grep -c で計上、CT_SRC_SUM を算出。stdoutへ「前日ConnectTimeout内訳: [源別ConnectTimeout] ...」を出力。
2. 観察レポート（critic-observe-YYYY-MM-DD.md）へ内訳行 `[源別ConnectTimeout] KENKAKU=N KCLUB=M KEMA=K CPMK=L（計S件）` と源別サブ4行（`  - KCLUB: M件` 等）を追記。既存3行（KENKAKU平均/ConnectTimeout総数/apply成功率）は維持。
3. ヘッダコメントに v146 の趣旨を追記。

## verification_evidence

$ bash -n /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-revenue-report.sh
SYNTAX_OK

$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-revenue-report.sh（本番実行・2026-09-15再生成）
- 前日ConnectTimeout: 47件/day
- 前日ConnectTimeout内訳: [源別ConnectTimeout] KENKAKU=11 KCLUB=14 KEMA=13 CPMK=9（計47/総47件）

$ grep -E 'KCLUB|KEMA|CPMK' /mnt/d/Project2/kensho/reports/critic-observe-$(date +%F).md | wc -l
4

受け入れ条件照合:
- 源別行が critic-observe-2026-09-15.md に存在 → PASS（本文に `[源別ConnectTimeout] KENKAKU=11 KCLUB=14 KEMA=13 CPMK=9（計47件）` plus サブ4行）
- 4源数値合計 = 既存ConnectTimeout総数 → PASS（11+14+13+9=47 = 47）
- 検証コマンド grep KCLUB|KEMA|CPMK → 4行 ≥ 3 → PASS
- 既存3行維持 → PASS（KENKAKU平均10.4件 / ConnectTimeout 47件/day / apply成功率91.2%）
- 禁止領域（応募ロジック・config・パイプライン・kenkaku.py）未_TOUCH → PASS（変更はスクリプト1ファイル+観察レポートのみ）

成果コミット: 97eff06（reports/critic-observe-2026-09-15.md、push済み 3c54d36..97eff06 main）
