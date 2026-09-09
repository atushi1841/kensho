# critic v50 — 2026-09-07 14:3x JST

## 0. 健康度
score=95 / priority=new_proposals / ready=0→1(v50投入) / blocked=0 / streak=0 / done=293

## 1. v48効果実測（PASS）
- monitor diff: `blocked=1→0, done=291→293, streak=5→0`
- worker 13:17 / qa 13:26 の出力で drift_skip 0件（10:45以前のpastチルのみ）
- 3ジョブ+evolution の cron 生存確認: nightly-critic next 16:20 / worker 14:45 / qa 15:10 すべて正常スケジューリング
- t_394b4655 done 確認済 → v48 クローズ

## 2. 新規提案 t_1a06aad4（中優先）
profile git（kensho-sweeps）の追跡ファイルが config.yaml 等2件のみで、
kanban_done_guard.py / tests/test_kanban_done_guard.py / reddit-gate-check.sh が untracked。
done-guard自体が「未コミットコード検出」をやる設計なのに、guard本体が版管理外=改悪時ロールバック不能（QA v49申し送り）。
- 成功指標: git ls-files scripts/kanban_done_guard.py 非空 + pytest 7 passed + status --porcelain 0行
- 検証: cd /home/atushi/.hermes/profiles/kensho-sweeps && git ls-files scripts/ | wc -l (>=1)
- 代替: profile repo不適なら /mnt/d/Project2/kensho へ移設しプロジェクトgitで追跡

## 3. 【要ユーザー対応】reddit G4（実機再確認）
reddit-gate-check.sh 14:29 実走: G4 FAIL = cookie_new.json は u/sabotenJAL(karma=1, 9/7作成) に紐づくが、
expected_account.txt=hbomax(karma=26935, 2023作成)。身元不一致のまま。
→ ユーザーが実際の投稿対象垢を確定し、その垢でF12再エクスポートが必要。G4が投稿をブロック中、cron 9689ecb38792 は paused のまま安全。

## 4. トリアージ
- t_355abea8 crowdfunding: done（v49 MVP縮小=CAMPFIREのみが機能）
- blocked=0 / ready=1 / scheduled=5（時間待ちは正しくschedule化済み、減点要因なし）
