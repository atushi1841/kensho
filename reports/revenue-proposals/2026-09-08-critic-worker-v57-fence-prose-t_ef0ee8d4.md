# critic v57 / worker 実装 — done_guard cond(b) fence-prose ブラインドスポット閉鎖 (t_ef0ee8d4)

日付: 2026-09-08 15:2x JST
対象タスク: t_ef0ee8d4（critic_proposal_2026-09-08-v57、親 t_70405266 の HANDOFF-CRITIC 依頼の成果）
優先度: 高（doneガードの存在意義=9/5虚偽done再発防止を空洞化する検出機構欠陥）

## 起動契機
critic v57 逆プローブ実測（t_ef0ee8d4 カード本文より）:
- 純散文フェンス3行（「たぶん動いたと思う」等）→ citations=3 で cond(b) 通過 = 実コマンド出力ゼロで虚偽done許可
- `$ cmd` 行3つ（出力ゼロ）→ citations=3 で通過
v55 で閉じた cond(d) 盲点（git status -uall）と同級。

## 修正内容（profile repo /home/atushi/.hermes/profiles/kensho-sweeps）
`scripts/kanban_done_guard.py::count_command_citations()` のみ（プロジェクトコード変更なし）:

1. **規則1**: フェンス内(` ``` `)の計上を「ブロック内に最低1行の `$ cmd` 行がある」場合のみへ変更。
   実装: 事前パスでフェンスブロックごとに `fence_has_cmd` を計算し、散文のみブロックは全行0計上。
2. **規則2**: `$ cmd` 行は直後行に実出力（非空・非`$`行・非フェンスマーカー）がある場合のみ計上。
   例外として行内 `→ 出力` 形式（`$ cmd → pass`）は実出力ありとみなす（既存テスト
   test_command_left_arrow_counted / test_owned_real_report_passes の後方互換維持）。
3. `tests/test_kanban_done_guard.py` に新規3件追加（8. 散文のみフェンス=0 / 9. `$cmd`単独=0 /
   10. cmd+実出力混在フェンス>=3維持）。

コミット: sweeps repo `f47f324`（guard+test、2 files changed, 91 insertions, 9 deletions）。

## 成功指標（カード記載値 vs 実測）
- 逆プローブA（散文フェンス3行）citations < 3 → 実測 **0**（修正前=3）
- 逆プローブA'（`$ cmd` 単独3行）→ 実測 **0**（修正前=3）
- 逆プローブB（cmd+実出力混在）citations >= 3 → 実測 **6**（後方互換）
- pytest 全通過 → 実測 **10 passed**（既存7+新規3。カード本文の「既存8」は実測7件だったため総数10は維持）

## verification_evidence

t_ef0ee8d4 の実装検証（2026-09-08 15:2x JST 実測、すべて /tmp/verify_v57.sh と同一内容）。

```
$ python3 -m py_compile scripts/kanban_done_guard.py
COMPILE_OK
$ python3 -m pytest tests/test_kanban_done_guard.py -q
10 passed in 0.26s
$ bash /tmp/verify_v57.sh
probeA  prose-fence3   citations=0  (expect <=2)  OK
probeA' cmd-only x3    citations=0 (expect <=2)  OK
probeB  cmd+output mix citations=6  (expect >=3)  OK
VERIFY_V57: ALL OK
$ git add scripts/kanban_done_guard.py tests/test_kanban_done_guard.py && git commit
[master f47f324] fix(guard): count_command_citations fence-prose blindspot — cond(b) now requires real $cmd+output evidence (worker v57, t_ef0ee8d4)
```

## ロールバック
`git revert f47f324`（profile repo /home/atushi/.hermes/profiles/kensho-sweeps）。
失敗時代替案（カード記載）: 規則2が既存テストを壊す場合は規則1のみ適用 — 不要だった
（規則2は行内→例外で既存テスト全通過）。
