# 検証記録: Dbmask（sealandseacat/dbmask）非API収益評価（t_bcf06c00）

- 対象: https://github.com/sealandseacat/dbmask / homepage: https://sealandseacat.github.io/dbmask/ / PyPI: https://pypi.org/project/dbmask/ / HN: https://news.ycombinator.com/item?id=49645189
- 判断: 却下（実装対象外）— 個人開発の「SQLデータベースの機密列を検出→決定的な偽データでマスキング→検証」する MIT ライセンスの Python CLI/ライブラリ（`pip install dbmask`）。収益化面（Cloud/SaaS/課金/API）が一切存在せず、Kensho が収集・加工・販売できる公開データセットも構造的にゼロ。スキルの却下濃厚パターン「OSS開発フレームワーク/OSSライブラリ（MIT等で無料配布）：収集データ・有料化余地なし → 却下」にそのまま該当。
- 検出は「自動化キーワード: あり」だが、これは製品内部機能（scan→mask→validate の自動ワークフロー、オプションの LLM 検出）の記述であり、自動収集・自動配信サービスではない = 誤検出除外枠（t_f000bf35 Egma、t_2647f10a Filament と同一パターン）。

## 3点評価

### 1) プロトタイプ — 不可
- このツールが扱うデータは「ユーザーが自前で持つ本番DBのコピー（PII）」であり、著者側にも第三者にも公開されている収集対象データはゼロ。模倣して作れる商品は「MIT OSS データベースマスキングツールの再配布」になる。
- 競合飽和: データマスキング/匿名化は既存プレーヤ多数（CrowdStrike Mockingbird、Caringo 系、PostgreSQL ネイスト、pgdbf、FFMUC Genercrypt、各DBベンダー有償機能、TDM で確立したカテゴリ）。個人後発で勝てるニッチ属性データがない。
- Kensho 資産（Python scraping + LLM 要約）を活かせる公開ソースが存在しない。

### 2) ローンチ手順 — 不可
- Kensho の配置経路（データAPI / 自動化スクリプト / 自前FastAPI / Apify/RapidAPI / ニッチSaaS）のいずれにも乗る商品性がない。PyPI で無料配布済み＋GitHub Pages ドキュメント付きで、有償版を差し出す余地がない（README 全文に pricing/cloud/enterprise 提供記載なし、MIT 単一ライセンス）。
- セキュリティ/ガバナンス製品（gdpr-consent、pii、security トピック）は信頼・監査実績が購買条件であり、無名の個人転売は構造通らない。

### 3) 集客 — 不可
- HN実測: points 5 / children 0（コメントゼロ）。スキル基準 score<20 で却下材料を大きく下回り、観客規模が微小。
- GitHub: star 132 / fork 21 / created 2026-06-09（約3か月）/ license=MIT / subscribers 10。集客アセット（属性データ / CtoA / 既存トラフィック / 移管可能な観客）は Kensho 側に一切ない。

## 結論
却下。worker 実装タスク（プロトタイプ/ローンチ/集客）は切り出さない。

## verification_evidence

```
$ curl -s "https://hn.algolia.com/api/v1/items/49645189" -o hn.json
author=SiyuanFeng points=5 children=[] created_at=2026-09-10T15:15:16.000Z
text=「I developed dbmask, an open-source Python tool designed to discover sensitive columns in SQL databases, masking them with deterministic fake values, and validate the masking results... LLM functionality is disabled by default... supports local execution via Ollama」（＝自前DB向けCLIツールの説明のみ。データ配布・API・収益面の記述なし）
$ curl -s "https://api.github.com/repos/sealandseacat/dbmask" -o gh.json
full_name=sealandseacat/dbmask stargazers_count=132 forks_count=21 subscribers_count=10
language=Python license=MIT created_at=2026-06-09T23:14:51Z homepage=https://sealandseacat.github.io/dbmask/
description="Discover, mask, and verify sensitive data in SQL databases — an auditable scan → mask → validate workflow"
topics=[anonymization,data-governance,data-masking,database,etl,gdpr-consent,pii,privacy,python,security,test-data]
$ curl -s "https://raw.githubusercontent.com/sealandseacat/dbmask/main/README.md" -o readme.md && grep -in -E "cloud|paid|pricing|enterprise|license|support|sponsor" readme.md
6:[![License: MIT]...] / 135:pattern detection... / 221:## Supported databases / 230:"supported by construction, verified by early adopters" / 269:If you need heavy-duty subsetting, synthesis, or enterprise scale today, / 319:## License / 321:[MIT](LICENSE)
（README 321行全文に Cloud/SaaS/課金/有償サポートの提供なし。冒頭は `pip install dbmask` ＋ SQLite デモ DB での scan→mask→validate クイックツアー。＝MIT単一ライセンスの無料OSSツール）
```

冒頭から証跡セクション末尾まで言及 task_id は t_bcf06c00（本タスク）のみ。
