# Verification Report — t_515d0237 (QA検証のSectioning化)

## 実施内容
nightly-qa ジョブ(033ff6065ef7)のプロンプトに「観点別分割検証（Sectioning化）」セクションを追加。
複数観点を1LLMコールで一括評価する従来方式を、観点ごとの個別LLMコール（delegate_taskパラレル）へ分割する指示に変更。
評価観点5分割（コード品質/BOT検出リスク/設計一貫性/テスト充足/ライブ計測）を全て取り上げるよう明記。

変更対象: `/home/atushi/.hermes/profiles/kensho-sweeps/cron/jobs.json` の nightly-qa prompt + hermes cron edit 反映。
応募パイプライン・config・モデル設定には一切非接触（低リスク・QAプロンプトのみ）。

## 適用方法（タスク定義通り）
1. QA検証プロンプトを観点別(コード品質/BOT検出/設計一貫性/テスト充足/ライブ計測)に分割 → **挿入済**
2. 各観点を個別LLMコール(delegate_task パラレル)で評価しスコア別に集約 → **プロンプト指示に明記**
3. 観点間で結論が食い違う案件ほど優先レビュー対象に浮上 → **プロンプト指示に明記**
4. 成功指標: QAが観点別検出を1タスクあたり平均1.2観点以上(現状0.5) → **プロンプトに埋込み**
5. 検証コマンド: grep -c 観点 cron/output/nightly-qa*.md → **プロンプトに埋込み**

## 検証エビデンス（実測）
```bash
$ python3 -c "import json;q=[j for j in json.load(open('/home/atushi/.hermes/profiles/kensho-sweeps/cron/jobs.json')) if j['id']=='033ff6065ef7'][0];print(len(q['prompt']), 'Sectioning化' in q['prompt'])"
=> 2707 True
```
```bash
$ hermes cron edit 033ff6065ef7 --prompt "$(cat /tmp/new_qa_prompt.txt)"
=> exit 0, Schedule 10 * * * * / Skills ai-team-improvement / Workdir /mnt/d/Project2/kensho（差分なし、他フィールド維持）
```
挿入ブロック冒頭: 「観点別分割検証（Sectioning化・t_515d0237導入）」が data に確実に反映済み。
プロンプト長: 1992→2707（+715字、スキルサイズ制約100KBの範囲内）。

## 自己レビュー（Reflexion）
```json
{"self_review":{"what_was_done":"nightly-qa(033ff6065ef7)プロンプトに観点別分割検証(Sectioning化)を追加。5観点をdelegate_taskパラレルで個別評価→スコア集約→観点間不一致案件の優先浮上を指示。","what_went_well":["既存1992字プロンプトの全文を保持したまま715字ブロックを挿入","hermes cron editでjobs.jsonに確実反映・他フィールド(Schedule/Skills/Workdir)維持","応募パイプライン・モデル設定・configに非接触"],"what_could_improve":["効果(平均観点検出1.2以上)の実測は今後のnightly-qa実行後に確認が必要","monitor_script/board_state_monitor_qa.shに変更不要か別途確認"],"mistakes_or_risks":["今夜のQA実行までSectioningが実際に動作するか未実証(低リスク・失敗時は単一QAパスへgit revert)","delegate_taskパラレルが5観点同時起動でコスト増の可能性(コスト効率モニタ継続)"],"learned":"QA検証品質向上はプロンプト指示のみでSectioningを導入できるが、実効果はQA実行ログ(grep -c 観点)で後続測定","confidence":8,"verification_evidence":"POST-EDIT prompt len=2707実測・'Sectioning化' in prompt=True・hermes cron edit exit 0 実測"}}
```

## 申し送り（QAへ）
- 本Sectioning導入の効果測定は今後のnightly-qa実実行にて: `bash ~/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh && grep -c 観点 ~/.hermes/profiles/kensho-sweeps/cron/output/nightly-qa*.md` で 0.5→1.2以上を確認。
- 失敗時は単一QAパスへ git revert（ロールバック候補）。
