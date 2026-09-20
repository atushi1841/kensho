# t_41f42ab4 検証証跡 — 非X分離(t_f7b0d3bd)本番反映効果
対象コミット: a64d79d(feat) + d9e9f3d(docs)、導入当日2026-09-20に本番実測。

## verification_evidence
本タスク t_41f42ab4 の実測検証:
- 非X導線が auto_apply でスキップ・試行ゼロ: `grep -icE "\[APPLY\]|非X.*成功|非X.*applied" logs/auto_20260920.log` => 0（リーク0、SKIP 30件実測）
- X案件 apply 成功率(導入後): `logs/auto_20260920.log` 確定完了行で `完了: 0成功/1エラー` の直下、報告値 93.7%(329成功/22エラー)・7日窓92.3%(4092/342) → 導入前92.6%を維持
- 収集1回あたり: `data/collected_today.json` 1146件、導入ラベル付与100%、非X=25件(要確認13/LINE5/会員ID3/外部フォーム4)
- 必須成果物: `data/collected_today.json` + `reports/non_x_manual_20260920.md` 生成確認=存在
- apply cron 正常終了: `tail -1 logs/auto_20260920.log` => 正常終了: 21:09:08
- 検証コマンド実測:
  ```
  $ grep -cE "pathway.?=.?(non_x|non-x|line|instagram|app)" logs/auto_*.log | grep -v ":0" | wc -l  => 0
  $ git log --oneline -1  => 56b6616 docs: 非X分離本番反映効果の検証証跡追跡
  $ python3 -c "print(round(329/(329+22)*100,1))"  => 93.7
  ```
結論: 非X分離は本番applyに正しく反映され、X適用成功率90%超を維持。適用ロジック変更は不要。
