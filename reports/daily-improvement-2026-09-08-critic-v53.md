# critic v53 — 2026-09-08 10:35 JST (kensho-revenue-critic / monitor起動)

## 0. 起動契機と健康度
- monitor差分: `score=95|ready=0|blocked=0|wip=0|prio=new_proposals|streak=0`
  → `score=100|ready=1|blocked=1|wip=0|prio=normal|streak=1`
- 変化要因 = 08:55にユーザー作成のMCPタスク(t_ff52eaf0)がblocked化、
  08:56にevolution(d340ec02d57e)がt_58335360をready投入。
- 終了時実測: score=80 / blocked=0 / running=4 / streak=0 / skip=False
  （減点理由は in_progress多3件 → worker側は完了優先中、正常な稼働状態）

## 1. トリアージ（blocked 1件）
### t_ff52eaf0 日本中古車価格 MCP Server → **revive (ready)**
- 分類: **復活可能**（構造的不能ではない）
- 根拠: `hermes kanban show t_ff52eaf0` のDiagnostics + log
  - run#261 timed_out 2971s / run#262 gave_up 2020s、両方
    `Iteration budget exhausted (90/90)`
  - run#262 の10:13 note: 「Diagnosing goo-net scraper parser vs live site
    (search-card selector / EUC-JP mismatch)」= **真因が特定済み**
  - log末尾に3ファイルの機械的修正プランが残っている:
    1. `src/main.py` — 死んだkeyword URLをCGI GET formに置換、
       78-81行のsilent fallback削除（失敗を全国在庫に化けさせない）
    2. `src/goonet.py` — charset固定euc-jpをresponse content-type基準に変更、
       CGI markup用セレクタ追加、keyword pathにPAGE=分页
    3. actor再ビルド → ハリアー/N-BOX/クラウンで再実行、`count >= 20`未満は
       "insufficient sample" を明示
- workerは `kanban_complete` を正しく呼んでいない（=虚偽done回避、prop11の規律どおり）
- 処置: `hermes kanban unblock t_ff52eaf0` + トリアージコメント
  → dispatcherが即claim（現在 running）
- 所見: **90 iteration上限に2回連続で当たっている**。修正プランは明確なので
  3回目も通る可能性はあるが、再発時は「scraper修正」と「公開検証」に
  タスク分割すべき（次回の申し送り）

## 2. ready供給の整備
### t_58335360 hear-saisei-boushi: all-status dedup guard
- evolution(d340ec02d57e)が08:56に作成、**assignee空** = dispatcherが
  「non-spawnable assignee」で永久スキップする既知パターン（2026-09-05教訓）
- 処置: `assign kensho-revenue-worker` → 即 running
- 内容: hunterが毎晩同じ案件をdone/archived込みで再生成する問題。
  Stripe式冪等キーを全ステータス照合に拡張。t_1a06aad4(v50)の系譜。

## 3. 新規提案（2件、priority=normal許容範囲）
### t_4e678707 crowdfunding 72h外部run判定（9/11 10:00）
- 実測: actor LSETMqsB30U9slWeU は **isPublic=True / modifiedAt 2026-09-08T01:01Z /
  build SUCCEEDED / runs=1 かつ唯一のrunはowner自身(userId VMz6nlpHoGIjTeSXS)**
- QA v51の申し送り「store未公開=72h KPI未開始」は **解消**（公開済み）。
  よってKPI時計は今日10:00 JSTから起動 → 判定は9/11。
- 成功指標: 外部(non-owner)run ≥ 1 OR u30d ≥ 1。検証コマンドはread-only curl+jq。
- 代替: 0なら実績あるREADME/タイトルSEO（t_5126f825）適用で第2ウィンドウ。
  **初回ミスでabandonしない**（Apify KYC可視性ゲートは別枠のユーザー対応）。

### t_a07ac34d RapidAPI 5本の無料オーファンBASIC版を解消
- 実測: `scripts/rapidapi_paid_effect.py --dry-run` が5本すべてで
  `⚠️ BASIC: 無料オーファン版に既存購読者 1人（中途解約自由）` を出力。
  有料BASIC($0.001)/PRO($0.005)/ULTRA($0.01)と**無料版が同居**しており、
  新規ユーザーが無料で逃げ込む経路が残っている。PAID購読者は全API 0。
- 成功指標: 同コマンドの `grep -c 無料オーファン版` が 0（or 実ユーザー例外1件の文書化）
- 代替: 有効購読者付きで削除不可なら、その版の価格を$0.001/callに上げて
  「無料の逃げ道」を塞ぐ。

## 4. other findings（提案化せず監視）
- profile git: `git ls-files` = 83 / `git status --porcelain` = 69 untracked。
  v50(t_1a06aad4)で gitignore + scripts/tests追跡は**完了済み**（QA PASS: ls-files 76→83,
  pytest 7 passed, porcelain 0 lines だったものがその後また69件）。
  → 大半は `bai_*.sh`(7) / `bin/` / `hooks/` / `images/` / `references/` /
    `scripts/apify_*.py` 診断系。done_guard自体は追跡済みでロールバック可能なので
  **BOT検出・自動復旧阻害ではなく低優先**。次回workerのgit整理に回す（新規タスク化は
  in_progress多の減点中なので見送り）。
- Gumroad売上ゼロ継続（$29.99 / 売上0）。販促はユーザー判断待ちの領域なので
  提案化しない（過去に却下済みアイデアの再提案禁止ルール）。
- reddit G4【要ユーザー対応】は継続中（cookie = u/sabotenJAL karma1 vs 期待 hbomax）。
  cron 9689ecb38792 paused のまま。ソフトウェアでは解決不可 → ステータス維持。

## 5. 申し送り
- worker: t_ff52eaf0 は3回目の90iter超過なら**タスク分割**（scraper修正 / 公開検証）。
- QA: t_a07ac34d の検証は read-only の `rapidapi_paid_effect.py --dry-run` で可能。
  課金プラン変更は破壊的なので before/after の plan version id を必ず記録させる。
- critic次回: running=4 が片付いてから新規提案。streak=0なので停滞なし。
