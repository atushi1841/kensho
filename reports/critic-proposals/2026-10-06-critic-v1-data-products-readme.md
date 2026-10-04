# Critic Proposal 2026-10-06 — README/CODEBASE にデータ商品セクション追加

## 背景（実測エビデンス）
- 外部ユーザー連続0日: 34日（Apify external_runs=0, Gumroad売上=0）
- GitHub リポジトリ atushi1841/kensho の README.md（139行）に「データ」「Apify」「Gumroad」「mercari」「dataset」のいずれも含まない（grep 実測: 2件のみ＝ディレクトリ構成と技術スタック参照）
- README_DATASET.md（57行）は別ファイルで、README.md から links されず、CODEBASE.md（93行）にもデータ商品セクションなし
- t_725c7a14 が GitHub Releases 週次公開＋dev.to/X 告知を実行中。リリースが増えても README に案内が無く、訪問者=Gumroad 誘導ルートが途絶える

## 提案
README.md と CODEBASE.md の末尾に「データ商品・外部API」セクションを追加し、
既存資産（Apify 86アクター、Gumroad 商品、GitHub Releases データセット）への導線を明示する。

## 収益ゲート準拠
- **誰が買う**: 日本市場データを必要とするデータサイエンティスト・市場分析者・EC開発者・研究者
- **どのチャネルで届く**: GitHub（README/CODEBASE 直載＝全访問者に表示）＋ 既存 dev.to/X チャネルと連動
- **30日で何が測れれば成功か**: GitHub README のデータ商品セクション链接を経由した Gumroad 商品view >= 50 / GitHub Releases DL >= 100（t_725c7a14 と連動）/ 外部ユーザー数 > 0
- **既存の何を再利用するか**: 既存 Apify 86アクター（PPE課金75件）、Gumroad 商品 agyhq、README_DATASET.md、t_725c7a14 の GitHub Releases パイプライン

## 成功指標（数値）
- README.md にデータ商品セクション追加後、Gumroad 商品view（UTM経由）>= 50/30日
- GitHub Releases 最新DL >= 100/30日（t_725c7a14 と連動測定）
- 外部ユーザー数 > 0（34日連続0の打破）

## 検証コマンド
```bash
grep -c "Gumroad\|Apify\|dataset\|data" README.md
curl -s https://api.github.com/repos/atushi1841/kensho | jq '.description, .homepage'
```

## 失敗時代替案
README編集が難航した場合は、GitHub Pages（gh-pagesブランチ）に製品ページを別途設置し、READMEからlinkする。最低限の変更（README末尾に1セクション追加）で済むように設計。

## 優先度: 中
- 理由: 外部流入0/34日継続の直接的要因の1つ（可視性不足）。t_725c7a14 と連動し収益直結。実装コスト低（1ファイル追加のみ）。
- リスク: 低（README編集のみ、テスト不要）