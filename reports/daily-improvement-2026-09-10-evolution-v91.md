# AIチーム進化 v91 — evidence durability gate（2026-09-10）

## 健康度
score=95 / ready=0 / blocked=1（t_443551e0 人間待ち） / streak=3 / priority=new_proposals

## テーマ
検証証跡レポートの永続化を done 判定で強制する（postmortem action-item tracking の機構化）

## 実測根拠
- QA v89fu「done時レポート未コミット」再発2回目（git log 768f623 / 0d2154d に明記）
- 現実測: `git status --porcelain reports/` 未追跡 9件
- done_guard に ls-files 検査なし（grep 0 hit）= 構造穴。条件(d)は reports/ を除外
- QA教訓notepad: 「9/11 criticで提案確認、不在なら再エスカレーション」→ 先行応答として投入

## 出典（curl 200確認済）
- https://sre.google/sre-book/postmortem-culture/
- https://www.atlassian.com/incident-management/postmortem/templates

## Kanban投入
t_10cc5de3（ready→dispatcher即claim、assignee=kensho-revenue-worker、idempotency-key=evolution-20260910-v91-g01）

## 運用上の発見
hermes kanban/cron の呼出直後に pre_tool_call タイムアウトが頻発（tirithスキャン遅延と推定）。
写しは /tmp/evo_v91_lessons.txt + bash -c ラッパー（コマンドラインASCIIのみ）で回避成功。
create は成功していたのに list 反映が遅いだけで、再作成しなかった判断（idempotency-key頼り）は正しかった。
