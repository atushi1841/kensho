# 非API収益評価レポート

- タスク: t_f5b4ac27
- 題目: Show HN: Wayfinder – A reference implementation for evaluating AI applications
- 元記事URL: https://news.ycombinator.com/item?id=49585201
- 対象URL: https://github.com/DivakarUngatla/wayfinder
- 報告元: kensho-non-api-revenue-hunter（score 3 / コメント 0）
- 評価日: 2026-09-07
- 評価者: kensho-revenue-worker

## 判定: 却下（非収益タスク・worker 実装タスクへ切り出さない）

Wayfinder は MIT 無料公開の AI Evaluation（LLMアプリのテスト技術: rule-based / LLM-as-a-Judge / offline / online eval 等）の「学習用リファレンス実装」OSS（description: "A reference implementation for learning and building AI evaluation systems"）。GitHub star 2 / 0 fork、HN score 3 / コメント 0。スクレイピング対象データ・公開API・ダウンロード可能DS・サーバー蓄積・収益要素が一切無く、Kensho 非API資産（Python scraping + LLM要約）をデータ商品に構成できない。過去却下の Engrim / Model ORM と同カテゴリ（無償OSS教育リファレンス）・同結論。

## 3点評価フレームワーク

### 1) プロトタイプ: 不成立
- Kensho 資産で対象となるスクレイピングデータが存在しない。対象は教育用コードベース（AI eval 手法の段階的実装）で、データ・API・DS なし。
- LLM評価手法の理論+サンプル実装は教育コンテンツであり、属性データ・再現困難データの独占性ゼロ。公開ソースの知識集約+LLM要約で誰でも再現できるコモディティ。

### 2) ローンチ手順: 不成立
- Kensho の配置経路（データAPI / 自動化 / 自前FastAPI / Apify/RapidAPI）に乗せられる商品要素がない。
- 有料化の余地なし（MIT・コードが無料配布、既存 LLM eval フレームワーク/コース多数で競合飽和）。ゼロからの手動教育事業は受動収益に非適合。

### 3) 集客: 不成立
- 集客アセット（属性データ / CtoA / 既存トラフィック / 既存観客）ゼロ。Repo star 2 / fork 0。
- HN score 3 / コメント 0 = 注目度がごく微小（score<20 且つ低コメント）。観客規模ゼロに等しい。

## 却下理由
- OSS無料公開の学習用リファレンス実装（MIT）で、収集データ・有料化余地・配置経路のいずれも構成できず、3点（プロトタイプ/ローンチ/集客）全て不成立。
- 自動化キーワード「reference/evaluating」は開発手法の教育記述で誤検出。経由元の HN 注目度（score 3）で観客規模も微小。worker 実装タスクへ切り出さない。

## Verification evidence
対象タスク: t_f5b4ac27（GitHub API / HN API 実測コマンド出力の引用）

- GitHub API リポジトリ取得（stars/forks/license/language/作成日時）:
```
$ curl -sL -m 25 "https://api.github.com/repos/DivakarUngatla/wayfinder" -o gh.json
HTTP 0 → 成功
"stargazers_count": 2
"forks_count": 0
"language": "Python"
"spdx_id": "MIT"
"created_at": "2026-07-12T16:08:34Z"
"pushed_at": "2026-09-06T07:42:15Z"
"description": "A reference implementation for learning and building AI evaluation systems."
```

- HN スレッド取得（score/コメント数/本文）:
```
$ curl -sL -m 25 "https://hn.algolia.com/api/v1/items/49585201"
"points": 3
"children": []
"author": "divakarungatla"
"text": AI Evaluation 学習用の自己紹介+フィードバック募集のみ（商業・収益要素なし）
```

- GitHub API 生JSON（stars/forks 等の生値確認）:
```
$ grep -E '"stargazers_count"|"forks_count"|"spdx_id"' gh.json
"stargazers_count": 2,
"forks_count": 0,
"spdx_id": "MIT",
```

## 検出パイプラインへの推奨除外ルール（追加）
- カテゴリ「アプリ/ツール」かつ対象が「OSS学習用リファレンス実装」（README に reference/learning/educational 等）で、収集データ・収益要素・配置経路を持たない場合、自動却下。
- MIT/Apache 等で無料公開済み && GitHub stars < 10 && HN score < 20 なら即却下。
