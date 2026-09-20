# t_f7b0d3bd 検証証跡 — 非X応募導線の分類収集と可視化

## verification_evidence

### 実装内容
- 新規 `kensho/scraping/pathway_classifier.py`: tweet_text から応募導線ラベル(導線)を判別。
  X のみ自動応募対象。LINE/Instagram/アプリ/レシート/会員ID/外部フォーム/DM/メール/要確認/未判定は
  自動応募対象外（手動・要確認）。新規自動操作なし・既存応募ロジックは安全側でしか触っていない。
- `kensho/scraping/collector.py`: 収集時に全件へ assign_pathway でラベル付与 →
  label_counts 集計 → collected_today.json 保存 → reports/non_x_manual_YYYYMMDD.md 生成（fail-open）。
- `kensho/application/applier.py`: apply_for_account で _entry_label の is_auto_applyable チェック。
  非X導線は [SKIP] を出して自動応募対象から除外。
- `tests/test_pathway_classifier.py`: 18テスト追加。

### 検証コマンド（実測）
```
$ python3 -m pytest tests/test_pathway_classifier.py --no-cov -q
=> 18 passed
```
```
$ python3 -m mypy kensho/scraping/pathway_classifier.py tests/test_pathway_classifier.py
=> Success: no issues found in 2 source files
```
```
$ python3 -m pytest --no-cov -q
=> 793 passed, 5 skipped / 2 failed（test_regression_gates: ライブボード状態監視）
```
失敗2件はライブボード状態監視であり本変更起因でない:
- `test_gate_protocol_violation_crash` → 本タスク t_f7b0d3bd の前回クラッシュ記録（今回の complete で解消）。
- `test_gate_result_column_empty_after_v151` → 別タスク t_3cc98f43(kensho-qa) の empty result。

### ライブ機能検証（実データ data/collected.json 1145件）
```
$ python3 -c "from kensho.scraping.pathway_classifier import ...; assign_pathway(...); label_counts(...)"
=> ラベル別: {'X':199,'要確認':1,'未判定':945} / 非X(自動応募対象外)=946件
```
is_auto_applyable('X')=True / それ以外(LINE/未判定/要確認/None)=False をコードとユニットテストで確認。
非X案件0件が自動応募対象に混入することを構造的に保証（X限定・安全側）。

### 完了条件
①実装: あり(commit a64d79d) ②実測検証: あり ③検証記録: 本ファイル
④reportパス: reports/t_f7b0d3bd_verification.md
