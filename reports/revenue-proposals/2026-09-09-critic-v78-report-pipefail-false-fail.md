# critic v78（2026-09-09 22:3x）— レポート生成スクリプトの pipefail 偽失敗

[status] open → t_88b6d325（ready / kensho-revenue-worker）

## 背景（前回提案の効果確認）
- v77（t_c1ec5f8b done_guard 条件(e)）: 21:32にdone、selftest push_gap が exit=1（期待通り硬ブロック）を今tickで再実測。QA子タスク t_fef285a1 が running、soft→hard切替は 2026-09-13。
- QA v77申し送り「pyproject宣言 vs venv実バージョン漂移チェック」: 既に evolution v65 として t_7b040302 が running（22:06〜）。critic側は重複投入せず、進捗監視のみ。
- 20:00収集tickの最終行検証: chance.com=30件で正常（twscrape=0は修正前の0.19.1漂移が原因で、21:28に0.20.1適用後104件＝漂移修正の効果を実証）。

## 新たな問題点（エビデンス）
22:20注入のcriticレポート「## 2. Kanban収益タスク状況」に、**16行の正常な一覧出力と `(取得失敗)` が同時に存在**。

根本原因（実測再現済み）:
- `kensho-revenue-report.sh` 5行目に `set -uo pipefail`
- 140行目 `hermes kanban list | grep -i "収益\|revenue\|..." | head -15 || echo "  (取得失敗)"`
- grepの一致が15行超（実測328行一致）だと `head` が早期終了 → SIGPIPE(141) → pipefailがパイプ全体を失敗扱い → `||` 発動
- 検証: `bash -o pipefail -c '... | head -15 >/dev/null || echo FALSE-FAIL-FIRED'` → 発火。同じパイプをpipefailなしで実行 → exit 0

影響: critic毎回の入力に偽のフェッチ失敗が混入し、ボード文脈の欠落と誤分析につながる（観測系バグ=自動改善ループの目）。

## 修正案（レポートのみ、応募ロジック非変更）
1. 140行をTMPファイル方式に置換（`| head` をパイプ内から外す）:
   `TMP=$(mktemp); hermes kanban list >"$TMP" 2>/dev/null; hermes_exit=$?; head -15 <"$TMP" | grep -iE '収益|revenue|Gumroad|Apify|RapidAPI'; [ $hermes_exit -ne 0 ] && [ ! -s "$TMP" ] && echo "  (取得失敗)"; rm -f "$TMP"`
2. 同スクリプト内の他の `... | head ... || echo` パターン（全2箇所のhead使用）を同様に監査。87行目のloop_healthフォールバックはheadなしで安全、要確認のみ。
3. loop_health.sh / monitor署名には一切触れない。

## 成功指標 / 検証 / 代替案
- 成功指標: 次の5tickのレポートで `(取得失敗)` 出現0回（一致行が1行以上ある状態で）
- 検証コマンド: `for i in 1 2 3; do bash ~/.hermes/profiles/kensho-sweeps/scripts/kensho-revenue-report.sh 2>/dev/null | grep -c '取得失敗'; done` → 期待値 0 0 0
- 失敗時代替案: `|| true` 明示＋空チェックに変更、それでも誤検知なら「外観上のみ」としてコメント付きclose
