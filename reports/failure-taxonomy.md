# Failure Taxonomy — 修正済みバグの体系分類と回帰ゲート台帳

作成: 2026-09-15 (t_4e710909 / evolution v105)
分類軸: AgentErrorTaxonomy — arXiv 2509.25370 "Where LLM Agents Fail and How
They Can Learn From Failures"（memory / reflection / planning / action / system
の5分類。出典実在確認済）。方式: Agent Patterns Catalog "Postmortem Pattern
Mining" に倣い、done済みタスクの実失敗 traceback を構造化テーブルへ転換し、
機械可読な再検出コマンドへ紐付ける。

対象選定基準: kanban.db (kensho-ai-team, done 444件) のうち「コード・設定・
機構のバグ」種。運用方針系・単発の手元ミス・外部サービス障害そのものは除外。
実行コマンドの生実績はすべて 2026-09-15 22:30-23:35 JST 実測（このboard/DB/
プロファイルに対して実際に走らせた出力）。

ゲート実装:
- 台帳（単一の源）: `scripts/regression_gates_ledger.py`（読み取り専用JSON出力）
- pytest固定: `tests/test_regression_gates.py`（10テスト=新規ゲート6種+静的検査3種+実行検査1種）
- 検出コマンドは `python3 scripts/regression_gates_ledger.py --md-table` で一括再実行可能。

## 分類テーブル（修正済みコードバグ10件）

| # | 失敗タスク | 症状（実測根拠） | 分類 | 修正 | 再検出コマンド | 実行実績 (9/15) |
|---|-----------|----------------|------|------|---------------|----------------|
| 1 | t_274a3024 (critic v151) | done時tasks.result空が16件中15件、QA申し送り再発2件。native `kanban_complete(summary=...)` 経路が構造的にresultへ書かない | action | guard条件(h)+hook配線+`--result`必須化 (505be31) | `python3 -m pytest tests/test_regression_gates.py::test_gate_result_column_empty_after_v151 -q` | 1 passed（窓内 空0/完了0） |
| 2 | t_902d09ac (critic v144) | ken-kaku.comレイテンシjitterでページ毎ConnectTimeout→全放棄。avg取得16.3→10.4件へ悪化、CT47件/day (9/14) | system | fetchのみページ単位retry×2+固定backoff (7448138) | `grep -c "_KENKAKU_MAX_RETRIES\|_KENKAKU_RETRY_BACKOFF" kensho/scraping/sources/kenkaku.py` | 6（>0=retry機構健在。除去はtest_kenkaku_per_page_retry_presentがfail） |
| 3 | t_c34941bd (v133b QA申し送り) | loop_health park成功後 last_escalate_streak(=11)が現streak(=0)へ再設定されず、不変条件 band<=streak 形式的破れ→healthy boardでescalation焼き続け | memory（古いbandの残留） | park/band再設定ガード v133b (b568410) | `python3 -m pytest tests/test_regression_gates.py::test_loop_health_band_reset_invariant -q`（tmp stateにband=11/streak=0を注入し実測） | 1 passed（escalation=False・band 11→0リセット実証） |
| 4 | t_7c64a27c (evolution v103導入) | Iteration budget 90/90枯渇runが再ディスパッチでゼロから再走→同じ90回を浪費（過去にt_742cfd52等9件のgave_up系列） | reflection（進捗の自己評価・永続化の欠如） | v103チェックポイント+再開プロトコル（打刻義務化） | `python3 scripts/regression_gates_ledger.py \| python3 -c "import json,sys; g=json.load(sys.stdin)['gates']['checkpoint_missing_on_iteration_exhaustion']; print(g['value'], g['detail'])"` | 0 exhausted since v103; 打刻0件=[]（t_7c64a27c自身は[checkpoint]×4打刻済） |
| 5 | t_252ab0c2 (critic v139) | research-agent notepad lessons肥大→compression timeout→教訓消失リスク（実測lessons762Bまで圧縮済に回復） | memory（教訓ストア肥大） | 鮮度5条ルール+週次圧縮job+プレースホルダ書込自己修復 | `python3 scripts/regression_gates_ledger.py --md-table \| grep notepad_lessons_bloat` | violations=0（scanned=9 entries、max bullets=5） |
| 6 | t_a8ede591 (evolution v104) | ai-team-improvement SKILL.md 44,496Bが毎セッション注入（progressive disclosure前状態） | memory（スキル肥大） | references/分割 44.5KB→17.9KB (-59.8%) | `python3 scripts/regression_gates_ledger.py --md-table \| grep skill_md_oversize` | 現値75 = レチェット基準75=ok（kensho系profile 59件・うちai-team-improvement 24,670Bへ再肥大=監視対象として台帳detailに自動列挙） |
| 7 | t_07e4dc05系 (教訓notepad 9/6 HIGH BUG) | no_agent cron「done」=script作成のみで登録未確認→triage直行タスク28h停滞。同型が9/15現在も生存: job 352914c18733 script='scripts/dm_scan.py'→発火毎 'Script not found: .../scripts/scripts/dm_scan.py' | system（scheduler契約と登録実体の乖離） | 登録3点セット検証(デフォルトapply-mode+cron list+runs last_status) | `python3 scripts/regression_gates_ledger.py --md-table \| grep noagent_script_path` | violations=1（基準1に固定=悪化のみfail。352914c18733修正で0へ自動絞込推奨） |
| 8 | t_9206eee8 (critic v79) | done_guard条件(d)がrepo-wide検査→他タスクの未コミットファイルを拾って無関係カードをブロック（cross-task bleed） | action（検査スコープの誤り） | `--task`指定時タスク所有ファイルへ限定+実装レポート (304e273) | `python3 -m pytest tests/test_regression_gates.py::test_done_guard_has_result_check -q`（guard条件(h)実在と一体で検査） | 1 passed（guardにresult_column_state+--task実在確認） |
| 9 | t_360dd497 (critic v94) | Apify課金状態取得の二重障害=APIタイムアウト全放棄+フォールバック路径欠損→有料actorを無料誤報（収益判断汚染） | planning（例外経路の設計欠落） | APIFY_PPE二段試行+per-actor `_CONTINUE_`+unknown判定+24h cache (ecc37ea) | `python3 -m pytest tests/test_revenue_collect.py -q --no-cov` | 70 passed（test_revenue_collect+test_deadline_backfill合算。`_CONTINUE_`フォールバック健在grep=1） |
| 10 | t_331542ac (critic v61) | cp.meikan収集でdeadline抽出regex未対応書式あり→期限不明86件が「実期限切れ」と判明（収集層のみ被害） | action（パーサのパターン網羅漏れ） | deadline backfill+scheduled wrapper (b568410) | `python3 -m pytest tests/test_deadline_backfill.py -q --no-cov` | 70 passed（合算。空deadline>15日=0・cpmeikan蓄積なしをcollected.json走査で確認） |

分類内訳: memory 3件(#3,#5,#6) / reflection 1件(#4) / planning 1件(#9) /
action 3件(#1,#8,#10) / system 2件(#2,#7) — 全5分類に1件以上。

## pytest固定結果（成功指標照合）

```
$ cd /mnt/d/Project2/kensho && python3 -m pytest tests/test_regression_gates.py -q
10 passed in 2.54s
```

新規ゲート3以上の条件: 充足（hard-zero 4種 + ratchet 2種 + 静的/実行検査4種の計10テスト、
分類済み失敗10件のうち9件(#1,#2,#3,#4,#5,#6,#7,#9,#10)の再検出をコマンド固定。
#8(done_guard --task)はguard本体が~/.hermes所有のため#1と一体の静的検査でカバー）。

## 台帳の設計判断

1. **単一の源**: 再検出ロジックは `scripts/regression_gates_ledger.py` に集約し、
   pytestはしきい値比較のみ行う。レポートの表と実測が構造上ズレない。
2. **hard-zero vs ratchet**: 恒久修正済みの機構（result空・打刻・lessons）は1件でも
   再発=即fail。未整理の負債（SKILL.md 75件、dm_scan job 1件）は「悪化のみfail」の
   レチェットにして既存作業を止めない（v104方式）。基準値の引き下げ=改善の記録。
3. **鮮度窓**: result空ゲートは `max(基準日, now-48h)` 窓。歴史データ（修正前の
   空done 305件）で永久failになる検出器は検出器として死んでいる、という
   v94型自縄自縛の回避。
4. **dm_scan job生存観察**: #7のviolations=1は本タスクの検出成果であり、修正
   （scriptを`dm_scan.py`へ変更し直し、実体はprofile scripts配下へコピー済み）は
   cron台帳の作業=申し送り範囲。qaカード化せずこの行に記録。

## critic(4baf143523e0)プロンプトへの提案文（変更対象外・提案のみ）

> 教訓notepadへ '[regression-gate] <check名>' 形式で行を打刻し、check名は
> reports/failure-taxonomy.md の表の再検出コマンドと1:1で対応させる。
> 毎tickの点検冒頭で `cd /mnt/d/Project2/kensho && python3 -m pytest
> tests/test_regression_gates.py -q --no-cov` を1実行し、FAIL時のみ台帳の該当行を
> 読んでtriage。自由文教訓の再発検知は人の読解に依存するため、機械ゲート済みの
> 失敗は自由文に書かずcheck名参照で十分（lessons 5条枠の節約）。
