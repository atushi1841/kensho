# critic v139 実装記録: kensho-research-agent notepad膨張修正 (t_252ab0c2)

日期: 2026-09-13 03:4x JST / ワーカー: kensho-revenue-worker

## 問題の実態（受け入れ条件本文との差分を含む）
- cron 0a52174180bd (kensho-research-agent、kensho-sweepsプロフィール所属) は
  9/12 12:19 に `Context compression timed out without reducing this conversation` で失敗。
- 実測した膨張源は `lessons` キー単体（620B）ではなく、research_* キー10本の合計 9,537B。
  notepadは毎run全文がプロンプトに注入される（scheduler.py:4698 render_notepad_section）ため、
  これがcompression timeoutの引き金。39d845fca735 (research-monetize) は同じ脚本を共有するがnotepad空。
- 退避先脚本: /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-research-agent.py
  （cron実行環境はHERMES_HOME=プロフィールを継承、workdir=/mnt/d/Project2/kensho、
    guardはプロンプト注入前=_build_job_promptより前に走るため同一runに効く）

## Change 1: notepad整理（実施済み）
- research_20260901〜20260911 の10キー全文 → /mnt/d/Project2/kensho/reports/research-YYYYMMDD.md へ移設（10ファイル）
- 旧 lessons（critic v51スナップショット）→ reports/research-lessons-archive-20260901.md へ退避
- lessons を新値5項目（簡条書き・全体671B）にset: 直近教訓3件+移設事実+運用手順
- research_* キーを全delete（移設ファイル実在確認後のみ）

## Change 2: 恒久ガード（脚本側）
main()先頭で notepad_guard() を実行（fail-open、例外は本体runを止めない）:
- research_* キー: 日付が3日超 → reports/research-YYYYMMDD.md へ全文退避してdelete；
  3日以内でも800B超 → 退避後「詳細: <path>」ポインタ行へtrim
- lessons: 2000B超過 → 全文を reports/research-lessons-archive-YYYYMMDD.md へ退避し、
  新しい行を後方から詰め直して ~1.9KB以内に圧縮 + アーカイブ参照行を先頭に付与
- 実施ログ: scripts/logs/notepad_guard.log
- 注入プロンプト末尾に【notepad保存ルール（必須）】を追加し、LLM自身にresearch_*キー新規作成を禁止

## ロールバック
- 脚本: git revert（kensho-sweepsプロフィールrepo）
- notepad: reports/research-*.md + research-lessons-archive-20260901.md に全文が残っており
  `hermes cron notepad 0a52174180bd set <key> "$(cat <file>)"` で復元可
  （実行には HERMES_HOME=/home/atushi/.hermes/profiles/kensho-sweeps が必要）

## 検証コマンド（QA向け）
notepadはdefaultプロファイルでなくkensho-sweepsのプロフィールローカルDBに存在する点に注意:

```
export HERMES_HOME=/home/atushi/.hermes/profiles/kensho-sweeps
hermes cron notepad 0a52174180bd get lessons | wc -c   # ≤2000 期待
hermes cron notepad 0a52174180bd list | grep -c 'research_2026' || true   # 0 期待
```

## verification_evidence

$ export HERMES_HOME=/home/atushi/.hermes/profiles/kensho-sweeps; hermes cron notepad 0a52174180bd get lessons 2>/dev/null | wc -c
671

$ export HERMES_HOME=/home/atushi/.hermes/profiles/kensho-sweeps; hermes cron notepad 0a52174180bd list 2>/dev/null | grep -E '^  [a-z_0-9]+ ='
  lessons = 2026-09-13 v139:

$ bash /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_252ab0c2/guard_selftest.sh
seeded: [('lessons', 1669), ('research_20260820', 1000), ('research_20260912', 2400)]
=== after guard ===
lessons: 102B | (古い教訓は /mnt/d/Project2/kensho/reports/research-lessons-archive-20260913.md に退避済み
research_20260912: 76B | 詳細: /mnt/d/Project2/kensho/reports/research-20260912.md（guard退避）
2026-09-13T03:37:00 compressed 0a52174180bd/lessons to 102B
2026-09-13T03:37:00 evicted 0a52174180bd/research_20260820 -> /mnt/d/Project2/kensho/reports/research-20260820.md
2026-09-13T03:37:00 trimmed 0a52174180bd/research_20260912 -> pointer /mnt/d/Project2/kensho/reports/research-20260912.md

$ ls /mnt/d/Project2/kensho/reports/research-2026*.md | wc -l
10

（合成テスト成果物 research-20260820.md / research-20260912.md / archive-20260913.md は検証後削除済み。
 実データ10ファイル+archive-20260901+新lessonsが正。）

## 成否指標の扱い
1. 9/13 12:00 run last_status=ok → 未来事象、QAの次tick検証へ（cron list for last_error drift）
2. lessons ≤2000字 → 671B PASS（上記実測）
3. compression timeout再発0/7日 → 継続監視。ai-context-monitor.sh が0a52174180bdを監視済
