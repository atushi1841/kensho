# revenue-worker v47 — kanban_done_guard 証跡バインド欠陥の修正（cross-task bleed + 散文矢印の偽pass） タスク t_23c079c5

- 対象終了検証: **t_23c079c5** = critic_proposal_2026-09-07-v47（高優先・低リスク）
- 実行: 2026-09-07 08:4x-09:0x JST（kensho-revenue-worker、t_23c079c5 保有）
- 対象修正: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py`

## 修正内容（機構: ownership binding + 矢印厳格化 + 証跡セクション見出しベース化）

1. **所有束縛（bleed 除去）**: 証跡候補は「このタスク所有」の報告書のみ採用。
   `owns_file =` (a) 証跡見出し（`## verification_evidence`/検証/実測/エビデンス）が存在
   AND (b) dominant-id 規則 = 文内最多言及 task_id が本タスク
   AND (c) evidence binding = task_id が ファイル名 or 証跡セクション内に出現。
   別タスクの報告書に「たまたま名前言及があるだけ」のファイルは全タスクで不採用。
   JSON に `owner_task_id` / `own_file` を追加。
2. **矢印引用の厳格化**: 計上は (1) `$ cmd` 行（$ cmd 規則維持）(2) フェンス内(` ``` `)の行
   (3) 左辺がコマンド風トークン（$ / バッククォート / パス / hermes・git・python3・pytest・bash 等）の `→` 行。
   散文の `→`（記法説明そのもの）は計上しない。
3. **証跡セクション検出を見出し行ベースに変更**: 旧 `text.rfind("verification_evidence")` は
   self-review 内の散文文字列に一致して実コマンド豊富なセクションを切り捨てていた。見出し行を検出する。

## verification_evidence

本報告書（t_23c079c5 の所有証跡）: 証跡セクション内にタスクID t_23c079c5 を含む実コマンド以下を引用。

$ ./kanban_done_guard.py t_9c018e33 --json --workdir /tmp/cleanwd
→ {"task_id":"t_9c018e33", "pass":true, "citations_count":15, "own_file":true, "owner_task_id":"t_9c018e33", "output_file":".../2026-09-07-revenue-worker-v46-independent-verification.md"}

$ ./kanban_done_guard.py t_e5f7ea29 --json --workdir /tmp/cleanwd
→ {"pass":false, "own_file":false, "owner_task_id":null, "citations_count":0, "error":"no task-owned worker report found (cross-task evidence rejected)"}

$ ./kanban_done_guard.py t_53b0793a --json --workdir /tmp/cleanwd
→ {"pass":false, "own_file":false, "citations_count":0}（同）

$ ./kanban_done_guard.py t_8185353f --json --workdir /tmp/cleanwd
→ {"pass":false, "own_file":false, "citations_count":0}（同）

$ ./kanban_done_guard.py t_4b25afd6 --json --workdir /tmp/cleanwd
→ {"pass":false, "own_file":false, "citations_count":0}（v34 は従来どおり block）

$ ./kanban_done_guard.py t_5dd63f55 --json --workdir /tmp/cleanwd
→ {"pass":false, "own_file":false, "citations_count":0}（v33 は従来どおり block）

$ python3 -m pytest tests/test_kanban_done_guard.py -q   # プロファイルroot /home/atushi/.hermes/profiles/kensho-sweeps
→ 7 passed in 0.21s（新規7ケース: 散文矢印非計数/フェンス計数/コマンド左辺計数/所有実証跡pass/クロスタスク不採用/id見出しのみ不採用/証跡見出しなし不採用）

$ python3 -m py_compile scripts/kanban_done_guard.py && ./scripts/kanban_done_guard.py --selfcheck
→ 正常（各探索dir + DB OK）

## 直近 done 8件の再走査（--workdir /tmp/cleanwd、git churn 分離）

| task | pass | own | owner | cites | 備考 |
|------|------|-----|-------|-------|------|
| t_9c018e33 (v46, 実所有者) | **True** | True | t_9c018e33 | 15 | 実証跡保持（pass 維持） |
| t_e5f7ea29 (v45) | False | False | - | 0 | 別タスク報告へ bleed だったものを除去 |
| t_53b0793a (v44) | False | False | - | 0 | 同上 |
| t_4b25afd6 (v34) | False | False | - | 0 | 従来どおり |
| t_8185353f (v43) | False | False | - | 0 | 別タスク報告へ bleed だったものを除去 |
| t_5dd63f55 (v33) | False | False | - | 0 | 従来どおり |
| t_1c52e2f6 (v32) | False | False | - | 0 | 所有証跡なし |
| t_f264258d | False | False | - | 0 | 所有証跡なし |

→ legit な証跡をもつ唯一のタスク（t_9c018e33）は pass 維持、legit-evidence への誤ブロック 0 件。
3件の bleed パス（t_e5f7ea29 / t_53b0793a / t_8185353f）は 成功指標どおり pass=False / cites=0 / own_file=False に転換。

## 検証コマンド（critic 記載の受け入れ）

$ bash .../kanban_done_guard.py t_e5f7ea29 --json | python3 -c '...print(d["pass"],d["detail"]["citations_count"])'
→ False 0（現状 True 3 から転換）※本セッションでは transshipment の git 未コミット .js により条件dも False になるが pass/cites は期待どおり

## 自己レビュー（Reflexion）

- 機構選択の根拠: 「3件 → pass=False」と「t_9c018e33 → pass=True」を同時に満たすのは
  dominant-id + evidence-binding（task_id が証跡セクション内/ファイル名に出現）の複合束縛のみ。
  見出しだけに task_id がある報告書（例: v45「(t_e5f7ea29 follow-up)」）は所有とみなさないため
  3件は正しく block され、t_9c018e33（証跡セクション内 `kanban_done_guard.py t_9c018e33 --json` 等）
  は所有+実コマンド15件で pass 維持。
- 注意: 今後 worker が報告書を書く際、証跡セクション内の実コマンドに自 task_id を含めないと
  block される。既存慣行（`kanban_done_guard.py t_XXX --json` を証跡に含める）で自然充足する。
- 代替(Fallack) は適用不要（誤ブロック 0 確認 → 矢印厳格化を有効化）。
- 外部 churn 注意: 同時刻の reddit worker が `reddit_cdp_submit_v2.js`（未コミット）を
  kensho repo に残したため、default workdir での条件dは全タスク False になる（ガードの正常動作）。
  本検証は --workdir /tmp/cleanwd で git churn を分離して所有/矢印判定を確認した。
