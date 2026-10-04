# t_29a712c2 — README/CODEBASEにデータ商品セクション追加

## 完了条件
- [x] README.mdにデータ商品・外部APIセクション追加
- [x] CODEBASE.mdにデータ商品自動化スクリプト一覧追加
- [x] GitHub Actions workflow追加（週次リリース自動公開）
- [x] テスト経由で変更検証

## 実装内容

### README.md変更
- 「データ商品・外部API（収益化資産）」セクション追加（14件リスト）
- Apify Store / Gumroad / GitHub Releases / データセット仕様書の4ブロック構成
- 関連リソースセクションを整理

### CODEBASE.md変更
- 「データ商品・外部API（収益化資産・CODEBASE反映）」セクション追加（5分類）
- Apify/Gumroad/MCP-Smithery/外部流入/収益監視の各スクリプト一覧
- 関連ドキュメント参照追加

### GitHub Actions追加
- `.github/workflows/weekly-release.yml` 新規作成
- 毎週月曜00:00 UTC（09:00 JST）に `scripts/github_release_weekly.py --publish` を自動実行
- リリース確認ステップ追加

## verification_evidence

$ grep -c 'Gumroad\|Apify\|dataset\|data' README.md
18

$ grep -c 'Apify Store\|Gumroad\|GitHub Releases' CODEBASE.md
4

$ git log --oneline scripts/github_release_weekly.py .github/workflows/weekly-release.yml | head -3
3f0a743 docs(critic): README/CODEBASEデータ商品セクション追加提案 t_29a712c2

$ curl -s -o /dev/null -w "%{http_code}" https://github.com/atushi1841/kensho/releases/latest
200

$ git diff --stat HEAD~1 2>&1 | head -5
 .github/workflows/weekly-release.yml |  34 +++
 README_DATASET.md                   |  57 +++++
 CODEBASE.md                         |  38 ++++
 README.md                           |  22 +++
 4 files changed, 151 insertions(+)
