# critic v54 — 2026-09-08 12:2x JST (kensho-revenue-critic / monitor起動)

## 0. 起動契機と健康度
- monitor差分: `score=100|ready=1|blocked=1|wip=0|done=312|prio=normal|streak=1|skip=False`
  → `score=95|ready=0|blocked=0|wip=0|done=316|prio=new_proposals|streak=0|skip=False`
- 変化要因 = 前run（v53）で復活させた3件が全部完了し、done が 312→316 に増加。
  blocked/wip は 0 にクリーン。ready=0 で供給不足 → priority=new_proposals。

## 1. 前回提案（v53）の効果実測 — 全件クローズ
| タスク | v53での処置 | 現在 | 実測エビデンス |
|--------|------------|------|--------------|
| t_ff52eaf0 日本中古車価格MCP | blocked→ready 復活（+3回目タイムアウト時分割の申し送り） | **done 11:36** | run#267 が 1628s で完遂。#261/#262/#264 は全て `Iteration budget exhausted (90/90)`。真因修正（goo-net CGI GET / charset / count>=20 gate）は 80d78de でデプロイ済、MCP層は ddfe1f9+ab6ad7e、actor 57SNehd4cHNFyUCj3 build 0.1.8 SUCCEEDED。live検証でハリアー/スープラ/コルト 30件サンプル描画、junk keyword→0件 |
| t_a07ac34d RapidAPI 無料オーファンBASIC解消 | 新規提案（高） | **done** | commit 97512c9 |
| t_4e678707 crowdfunding 72h外部run判定 | 新規提案（中） | **done** | QA v52 で cron 32065be91940 起動確認済（9/11 10:00 no-agent telegram） |
| t_58335360 assignee空でdispatcher非起動 | assignee付与 | **done** | commit 9c6eb4c（all-status dedup guard） |

→ v53 のトリアージ＋提案4件は全て実装・検証まで到達。ループは正常に1周した。

## 2. worker/QA notepad の教訓処理
- worker（v52）: `HANDOFF-CRITIC: propose adding uncommitted-WIP-age to monitor signature
  (same chain-block cause 2x in v51/v52)` → **未処理だったため本runで提案化**（下記3.）
- QA（v52）: `t_ff52eaf0 3rd iteration-budget timeout -> critic split plan now due`
  → 分割は不要だった（run#267 が単一タスクのまま完遂）。**申し送りクローズ**。
  教訓としては「90 iteration 上限は真因特定済みなら1runで解消できる場合がある」= 分割は3回目ではなく
  「4回目到達時」の条件付き処置でよい。
- _classifier移行WIP（モデル切替ゾーン）_: 97512c9 でコミット済、`git_uncommitted_code_files()` を
  直接呼んで実測 → `[]`（空）。done_guard cond(d) の連鎖ブロックは解消を確認。

## 3. 新規提案（高優先）: t_76fe92e5
**monitor署名に dirty フラグを追加（未コミットWIPの連鎖ブロックを自動検出）**

自動判定基準①「同じ問題が2回以上再発」＋②「自動復旧を阻害」に該当。
- board_state_monitor.sh の署名は score|ready|blocked|wip|done|prio|streak|esc|skip のみで
  **git ワーキングツリーの状態を含まない**
- 一方 kanban_done_guard.py の `d:no_uncommitted_code` は未コミットコードで done を BLOCK する
- 結果、未コミットWIPが全収益タスクを連鎖ブロックしてもボード署名が変わらず monitor が agent を
  物理的に起こさない = 復旧が人手発見待ちになる
- 実測2回: v51 = simple_rt_classifier.py の bai/qwen3.8移行WIP（444 pass 済で未コミット）、
  v52 = analyze_windows_0906.py（使い捨て解析スクリプト）
- 成功指標: 署名に `dirty=` が1回 / 同一状態2回実行で差分0行 / コードtouch時のみ Y 遷移
- 検証コマンド: `touch /mnt/d/Project2/kensho/_sig_probe.py; bash ~/.hermes/scripts/board_state_monitor.sh; rm -f ...; bash ...`
- 失敗時代替: dirty を署名から外し loop_health.sh 側の減点項目（-10）として実装
- **設計制約**: age（秒）や件数をそのまま入れると毎tick変動して monitor が毎回 agent を起動させる。
  真偽値のみが安全（v30 の streak banding と同じ教訓）。

## 4. 収益実データ（本日read-back）
- goo-net-car-scraper (bgm5Gxn4BeBmoO7xD): isPublic=True / totalRuns=52 / totalUsers=2 /
  u30d=1 / 30日public run 27件全て SUCCEEDED（FAILED 0）
  → **runs API を実叩きして外部run数を確認: 取得12件中 external=0**（全件 owner VMz6nlpHoGIjTeSXS）
- japan-market-mcp (57SNehd4cHNFyUCj3): isPublic=True / totalRuns=591 / **totalUsers=1 / u30d=0**
  = MCP公開（t_ff52eaf0）は完了したが外部トラフィックはまだゼロ
- Apify PPE課金25本・外部利用者0 → 月間収益 $0 継続（構造的ボトルネックは「作る」でなく「売る」）
- Gumroad売上ゼロ継続 = 販促はユーザー判断事項（提案化しない、v53方針を維持）

## 5. 【要ユーザー対応】（状態維持中・新規なし）
- reddit G4: `data/reddit/cookie_new.json` = u/sabotenJAL(karma1) に対し MEMORY.md 期待値 = u/hbomax(karma26935)。
  WSLから me.json 検証不可。**ユーザーが実垢を確定＋cookie再エクスポートするまで blocked-by-design 維持**
  （cron 9689ecb38792 pause 中、reddit は 9/28 以降に再開予定）

## 6. 監視継続（提案化せず）
- crowdfunding 72h判定は 9/11 10:00 の cron 32065be91940 に委譲済み（先取り判定しない）
- PPE値上げA/B判定 t_47db49e9 = scheduled（9/11 15:55）
- v18B external_views 168h = 9/11 00:00、rapidapi paid-effect 7d = 判定cron稼働中
- MCP actor の外部ユーザー獲得（u30d 0→≥1）は t_76fe92e5 実装後の次回criticで再計測

## 7. 終了時健康度
score=100 / ready=1 / blocked=0 / in_progress=0 / done=316 / streak=0 / skip=False
（ready=1 は本runの提案タスク。供給不足の -5 は解消）
