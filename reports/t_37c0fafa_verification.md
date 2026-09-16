# t_37c0fafa 検証証跡 — critic v162 ハンター発券重複防止ガード (2026-09-16)

## 変更ファイル
- scripts/kensho_hunter_guard.py (新規 346行): 決定的キー生成 + openカード走査 + コメント代替 + CLI check
- kensho-non-api-revenue-hunter.py (修正): create_kanban_task が hunter-YYYYMMDD-<hash8> キー必須化、guard-skip 分岐追加
- scripts/kensho-opportunity-discovery.py (新規): cron発券プロンプトが guard check + --idempotency-key 必須を指示 (L149-154)
- tests/test_hunter_guard_v162.py (新規 330行): 要件1-3+統合の回帰テスト
- SOUL.md (kensho-revenue-worker / メモリ): 発券前 guard check 絶対ルール投入済み

## セルフ検証実行記録

$ python3 -m pytest tests/test_hunter_guard_v162.py -q
17 passed in 19.83s

$ python3 -m py_compile kensho-non-api-revenue-hunter.py scripts/kensho_hunter_guard.py
COMPILE_OK

$ python3 scripts/kensho_hunter_guard.py check --title '日本物件ハザードリスクMCP プロトタイプ作成' --body '住所から洪水・土砂リスクを判定するMCPサーバー'
[hunter-guard] BLOCKED dup-theme: -> 既存 t_06fdd792 (共通語 ['b:bridge:サーバー', 'b:bridge:ハザード', 'b:bridge:リスク', 'b:bridge:住所', 'b:bridge:土砂', 'b:bridge:洪水'] 他2件)
exit=1 (実事例 t_c3af4776≡t_06fdd792 の cross-lingual 二重登録を検出)

$ python3 scripts/kensho_hunter_guard.py check --title '無関係な新規テーマ: 宠物用自動餌やりApifyスクレイパー' --body '全く別物'
hunter-20260916-195337ba
exit=0 (決定的キー出力、誤検知なし)

## 回帰（フルスイート）
638 passed, 3 failed — 3件とも本タスク変更と無関係な既存赤（git stash 对照で pre-existing を実証済み、t_37c0fafa の差分なしでも同一3件FAILED）
