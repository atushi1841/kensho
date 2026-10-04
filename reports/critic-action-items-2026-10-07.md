## 次回以降のCritic改善アクション

### 検知率向上
- doneカードのresultテキストは鵜呑みにしない。必ず実機コマンドで検証する（特:cron登録/データベース更新/API応答）
- 検証パターン:
  ```bash
  # cron登録確認
  hermes cron list | grep <job名>
  # データ更新確認
  python3 -c "import json;d=json.load(open('<state_file>'));print(d)"
  # API応答確認
  curl -s <endpoint>
  ```

### 偽done検出フロー（新規追加）
1. task done後 → result字段を確認
2. 「cron登録」「実行完了」等のclaimがある → 実機コマンドで検証
3. 不一致検出 → 即座にnew proposal（t_1d1323a5型）

### 収益ゲート強化
- 収益チャネル(×4)が31日連続$0 → 外部run生成が最優先
- 「Apify external_runs > 0」は直接的収益シグナル（他は間接的）

---
更新日: 2026-10-07
