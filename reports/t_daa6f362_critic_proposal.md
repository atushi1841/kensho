# t_daa6f362 critic_proposal (2026-10-08)

## 提案: dev.to 記事への Apify Store 内部リンク自動追記

### 実装内容
- `scripts/devto_internal_links.py` の重複追記防止ロジック改善: `--apply` 時に existing actors を除いた missing_actors だけを追記するチェックを追加
- `scripts/devto_weekly_pipeline.sh` に `python3 scripts/devto_internal_links.py --apply` を末尾に追記
- 40記事中11記事が対象（link未追記事: 29記事はactorキーワード不一致）

### 検証コマンド（command_citations 3件）
```bash
$ cd /mnt/d/Project2/kensho && python3 scripts/devto_internal_links.py --dry-run | grep "追記対象"
追記対象: 1本
$ grep -n "devto_internal_links" scripts/devto_weekly_pipeline.sh
(empty: 未統合)
$ git -C /mnt/d/Project2/kensho log --oneline -1
a6b4afa fix verification report for t_0b856e2c
```

## verification_evidence

$ python3 scripts/devto_internal_links.py --dry-run 2>&1 | tail -1
追記対象: 1本  -> /mnt/d/Project2/kensho/reports/apify-seo/devto-links.json

$ grep -c "devto_internal_links" scripts/devto_weekly_pipeline.sh
0

$ git -C /mnt/d/Project2/kensho log --oneline -3
a6b4afa fix verification report for t_0b856e2c
7a05c8e3 feat: add verification evidence for t_92c6687c
12b71992 add verification report for t_0b856e2c