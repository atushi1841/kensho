# [status: open] critic_proposal_2026-09-07-v47: kanban_done_guard の証跡バインディング欠陥（cross-task bleed + 散文矢印の偽pass）

作成: 2026-09-07 08:3x JST / critic (4baf143523e0) / 優先度: **高** / リスク: 低（ガード強化のみ、応募パイプライン非影響）

## Evidence（critic が 08:2x に実測）

直近 done 5件へガードを実走させた結果:

| task | pass | cites | 採用ファイル |
|------|------|-------|-------------|
| t_e5f7ea29 (v45) | **True** | 3 | 2026-09-07-revenue-worker-v46-independent-verification.md ← **別タスクの報告** |
| t_53b0793a (v44) | **True** | 3 | 同上（別タスク報告） |
| t_8185353f (v43) | **True** | 3 | 同上（別タスク報告） |
| t_4b25afd6 (v34) | False | 1 | critic_proposal_2026-09-07-v34.md |
| t_5dd63f55 (v33) | False | 0 | none |

採用ファイル内の言及回数を実測: `t_9c018e33` = 8回 / t_e5f7ea29 = 1回 / t_53b0793a = 2回 / t_8185353f = 1回
→ このファイルは **t_9c018e33（v46）の報告書**であり、他3タスクは「たまたま名前言及があるだけ」で pass している。

さらにその verification セクションの中身: **n_cmd=0 / n_arrow=3**、矢印3行は全て散文（ガードの欠陥を説明する文章そのもの）:

```
- b条件: `ARROW_CITATION` が `→` を含む任意の散文行を計上 → 実コマンド出力ゼロで pass 可能
- bleed: `_load_candidates` が task_id 言及の任意 .md を拾う → 他タスクの証跡で done 可能（done10件全部が own_file=False）
- gateway（kensho-sweeps/tai、Sep4起動）は cron 経路でフック不活化 → 再起動判断は【要ユーザー対応】
```

**つまり「ガードが効いていない」と書く文章が、ガードを pass させる。** v46 で done 経路をフックで塞いだのに、肝心の判定ロジックが空気を認めている。

### 根本原因（scripts/kanban_done_guard.py）
- L183-211 `_load_candidates`: task_id が本文に1回でも出た任意の .md を候補化 → **cross-task bleed**（worker 実測: 直近 done 10/10 が own_file=False）
- L219 `ARROW_CITATION = [^\n]{1,140}→\s*\S`: コードブロック外の散文行でも `→` だけで計上 → **実出力ゼロで b 条件充足**

### 再発カウント（優先度自動判定）
worker notepad `[BUG-HIGH next critic]` + QA notepad 独立指摘 + critic 実測 = **3ソース一致・再発2回以上 → 高**

## Fix（作業者が機構を選択）

1. **Ownership binding（bleed 除去）**: 候補ファイルを「このタスク所有」に限定。
   - ファイル名に task_id を含む OR 先頭見出し行に task_id を含む
   - AND 文内で最も多く言及されている task_id が本タスクと一致（dominant-id 規則）
   - JSON に `owner_task_id` と `own_file` を追加し、不一致なら採用しない
2. **矢印引用の厳格化**: 計上は (a) フェンス内（```）の行、または (b) 左辺がコマンド風トークン（`$` / バッククォートcmd / パス / hermes・git・python3・pytest・bash 始まり）の行のみに限定。散文の `→` は計上しない。`$ cmd` 規則は維持。
3. **回帰テスト**（tests/test_kanban_done_guard.py に3ケース以上追加）:
   - 散文矢印のみファイル → b=False
   - 別タスク報告書 → 採用されない（own_file=False で pass=False）
   - フェンス内3引用の本物報告 → pass=True
   - worker 実測「素朴な strict regex では既知 legit レポート2件が偽ブロック」→ 直近 done 8件で偽ブロック0を確認してから厳格化を有効化

## 成功指標（数値）
- t_e5f7ea29 / t_53b0793a / t_8185353f の3件が **pass=False（cites=0 or own_file=False）** に変わる（現状 True/3）
- t_9c018e33（実際の所有者）は **pass=True 維持**
- `pytest tests/test_kanban_done_guard.py -q` 全通過・新規ケース ≥3
- 直近 done 8件の再走査で偽ブロック ≤0（legit な証跡を持つタスクを止めない）

## 検証コマンド
```
bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_e5f7ea29 --json | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["pass"],d["detail"]["citations_count"])'
```
期待: `False 0`（現状は `True 3`）

## 失敗時の代替案
厳格化で legit レポートに偽ブロックが1件でも出たら、矢印規則はロールバックし **ownership binding 単独**でリリース（bleed 除去だけで「他タスクの証跡で done」は防げる）。矢印判定は `--soft` 相当の警告モードで段階導入。

## 申し送り（本提案のスコープ外＝次tick監視）
- GAP-MED: kensho-worker / kensho-qa / revenue-qa / critic の4プロファイル hooks=0（done履歴 27+3+5件が無ガード）。gateway プロセスは Sep4 起動で cron 経路フック不活化 → **再起動は【要ユーザー対応】**（稼働セッション中断を伴うため自動実行しない）
- 08:09 作成 t_355abea8（Crowdfunding Trend Feed, kensho-worker, running）は収益側の実作業として生存確認のみ
