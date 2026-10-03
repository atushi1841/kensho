## verification_evidence

### 実装内容
- config.yaml の orchestrator.priority を "pending_first" から "competition_score" に変更

### 検証コマンドと結果

$ grep "priority:" config.yaml | head -3
  priority: competition_score
  priority_multipliers:

$ python3 -m pytest tests/test_competition_sort_logic.py -xvs 2>&1 | tail -5
============================== 2 passed in 40.78s ==============================

$ python3 -m pytest tests/test_competition_scorer.py -x -q 2>&1 | tail -3
======================= 14 passed, 2 warnings in 15.44s =======================

$ python3 -c "import json; d=json.load(open('data/competition_score.json')); print('real entries:', len(d))"
real entries: 395

$ git log --oneline -3
b4fbbeb fix(t_dd7f5e39): update verification format for guard
a3dba35 fix(t_dd7f5e39): orchestrator priority to competition_score + sort logic test
a767438 fix(revenue-health-check): add missing fields and defensive .get from kensho-sweeps profile

### 成功指標
- orchestrator.py: priority=competition_scoreブロック動作確認（テストPASS）
- config.yaml: priorityがcompetition_scoreに変更
- competition_score.json: 395件実データ存在
- バッチ配分でpending多いアカウントへ優先配分（sort_key実装済み）

### 失敗時代替案
- fallback: round_robin（既存挙動維持）
- 収集失敗: kensho_cron_workerの既存エラー処理に委譲

---
カード: t_dd7f5e39
