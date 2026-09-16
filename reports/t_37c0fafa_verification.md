# t_37c0fafa 検証証跡 — critic v162 ハンター発券重複防止ガード (2026-09-16)

## 変更ファイル
- scripts/kensho_hunter_guard.py (新規): 決定的キー生成 + openカード走査 + コメント代替 + CLI check
- kensho-non-api-revenue-hunter.py (修正): create_kanban_task が hunter-YYYYMMDD-<hash8> キー必須化、guard-skip 分岐追加
- scripts/kensho-opportunity-discovery.py (新規): cron発券プロンプトが guard check + --idempotency-key 必須を指示
- tests/test_hunter_guard_v162.py (新規): 要件1-3+統合の回帰テスト
- 受け入れコミット: 4bf5e83

## verification_evidence

$ python3 -m pytest tests/test_hunter_guard_v162.py -q
17 passed in 13.70s

$ python3 -m py_compile kensho-non-api-revenue-hunter.py scripts/kensho_hunter_guard.py scripts/kensho-opportunity-discovery.py
COMPILE_OK (exit 0, t_37c0fafa)

$ python3 scripts/kensho_hunter_guard.py check --title '日本物件ハザードリスクMCP プロトタイプ作成' --body '住所から洪水・土砂リスクを判定するMCPサーバー'
[hunter-guard] BLOCKED dup-theme: -> 既存 t_06fdd792 (共通語 ['b:bridge:サーバー', 'b:bridge:ハザード', 'b:bridge:リスク', 'b:bridge:住所', 'b:bridge:土砂', 'b:bridge:洪水'] 他2件)
exit=1 (実事例 t_c3af4776≡t_06fdd792 の cross-lingual 二重登録を検出、t_37c0fafa 要件2/3)

$ python3 scripts/kensho_hunter_guard.py check --title '無関係な新規テーマ: 宠物用自動餌やりApifyスクレイパー' --body '全く別物'
hunter-20260916-195337ba
exit=0 (決定的キー hunter-YYYYMMDD-<hash8> 出力、誤検知なし、t_37c0fafa 要件1)

$ git log --oneline -1
4bf5e83 feat(guard): t_37c0fafa critic v162 ハンター発券重複防止 — 決定的キー hunter-YYYYMMDD-<hash8> 強制 + 起票前open走査 + コメント代替

## 回帰（フルスイート）
638 passed, 3 failed — 3件とも本タスク変更と無関係な既存赤（git stash 対照で pre-existing を実証済み、t_37c0fafa の差分なしでも同一3件FAILED）。

## 成功指標の今後の計測
完了後7日間の worker発券 idempotency_key NULL 件数はQA側の定期計測カードで追跡（本カード起働時点ではウィンドウ未経過）。
