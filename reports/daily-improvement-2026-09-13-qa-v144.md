# QA run455 — インシデント検証・復旧報告（2026-09-13 20:0x）

## 結論: 軽重大インシデント検出→追跡ファイル32件復旧済。ただしgitignoreデータは復旧不能（【要ユーザー対応】）

## トリガ
monitor差分 `blocked 0→1 / dirty N→Y`。内訳確認中に **9/13 18:0x〜18:30 発生の一括削除インシデント**を検出。

## インシデント概要（実測）
- `git status` に **追跡ファイル32件の未ステージ削除（D）** を発見（scripts/audit_bot_safety.py・scripts/dm_scan.py・gen_status_*・tests/test_audit_bot_safety_regularity.py・reports/improvement-anchor.md・critic_proposal 17件・daily-improvement系 等）
- 32件中29件は本文に `chugakujuken` を含む → **chugakujuken除去delegateタスク（18:03起動の hermes_kernel_runner PID206246、cwd=/mnt/d/Project2/kensho）が「言及ファイル削除」に拡大した疑い**。chugakujuken除去そのものはユーザー委任済みだが、ファイル削除は委任範囲外
- gitignoreデータの同時消失（git復旧不可）:
  - `data/audit.jsonl`（セッション跨ぎ重複アクション防止台帳・SHA256チェーン）→ 17:36時点の履歴消失確定
  - `data/x_session.json`（**atushi16=自宅IP主垢**）→ 18:30:16ログに初「セッションファイルなし」、9/12ログは0件で前日までに正常。Credential Managerにも `kensho-sweeps` エントリなし（cmdkey実測）＝**復旧経路なし**
  - `data/x_session_TankanNotes.json` 同様消失
  - `logs/2026-09-12/` 全消去・`logs/2026-09-13/` は18:30以降のみ残（collectも11run→2runに）。summary/*.mdは生存
- 削除系はD:\$Recycle.Binに9/13 17:00以降の$Iエントリなし（実測）＝ごみ箱経由復旧不可

## QA対応（実施済）
1. `git restore` で32件全復旧 → 残D=0。py_compile/bash -n/all suite **pytest 568 passed・4 skipped**
2. `scripts/audit_bot_safety.py --today` 復旧後exit 0（audit.jsonl再作成→「成功アクションなし」正常応答）
3. `scripts/kensho-dm-scan.sh` の `Single '}' encountered in format string` バグ修正（`'（累計記録: {}件}'`→`'（累計記録: {}件）'`）。dm-winner-check 9/13 10:00 runがこのバグでLAST=errorだった
4. 被害dataスナップショット `data/backups/incident-20260913/` に10ファイル退避
5. 残存chugakujuken差分（config.yaml他20ファイルdirty=Y）は critic notepadどおり**ユーザーコミット判断待ち**でQAからはコミットしない

## 残存リスク
- 今夜の重複アクションリスク: audit.jsonl空=セッション跨ぎdupガード無効。ただし collected.json の applied+日次カウント（daily_counts.json生存）+ハードキャップ100件は有効なので限定リスク。翌朝のaudit.jsonl/summary突合で確認要
- atushi16/TankanNotes はバッチ毎に0成功/1エラーで失敗継続（ブラウザgotoタイムアウト Logs 19:19実測）＝実質応募停止

## 【要ユーザー対応】
- **atushi16（自宅IP主垢）とTankanNotes のX再ログイン → auth_token/ct0再保存**（ブラウザログイン→セッショントークン抽出。物理操作のため自動化不能。9/1 zin/toushiwatch復帰時と同手順）
- chugakujuken除去差分20ファイルのコミット可否判断（垢構成変更=確認必須領域）

## 3軸評価
```json
{"evaluation":{"technical":{"score":5,"assessment":"delegateタスクの削除拡大でgit追跡32件+gitignoreデータ消失。追跡分は完全復旧、データ分は不可","evidence":"git status D=32→restore後0、pytest 568 passed、x_session.json/audit.jsonlはkeyring・ごみ箱とも復旧経路なし実測"},"business_kpi":{"score":6,"assessment":"atushi16/TankanNotes応募が実質停止（主垢=日次100件枠の屋台骨）。収集・他垢は正常（19-20時 230件系collect稼働）","evidence":"orchestrator 18:30-20:08ログ『セッションファイルなし』+0成功/1エラー継続"},"cost_efficiency":{"score":8,"assessment":"復旧はgit restore+テスト再走でLLM追加起動なし、dm-scanバグ修正で次回error防止","evidence":"git restore 1回・pytest 69s・bash -n"}},"loop_health":{"score":100,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":false,"notes":"delegate/chugakujuken除去実施側は削除前にgit ls-files差分確認と『削除は委任範囲外』の自己レビューを欠いた（プロセス改善: 削除系操作は git rm 明示+カード承認必須へ）"},"verdict":"conditional_pass","next_steps":["atushi16/TankanNotes再ログイン（要ユーザー）","翌朝audit.jsonl再蓄積とdup突合","chugakujuken差分コミット判断","criticへ『削除系delegateはgit rm+範囲宣言必須』提案化"]}```
