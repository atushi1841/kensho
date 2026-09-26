# 評価レポート: Ask HN: Does a startup need both founder and company X accounts? (task t_b0e41cef)

- Task: t_b0e41cef
- 対象: https://news.ycombinator.com/item?id=49837729 (task t_b0e41cef)
- 元記事URL: https://news.ycombinator.com/item?id=49837729
- カテゴリ: アプリ/ツール / 非API自動収益
- 判断: **却下（非収益・実装対象外）** (task t_b0e41cef)
- 実装工数推定: 適用外（単なる起業家の悩み相談スレッドであり、プロダクト・データ・ツールが存在しない）

## 対象の実態（実測）
本件は Hacker News の Ask HN 投稿であり、プロダクトのローンチ・データ・API・スクレイピング対象ツールではなく、**個人起業家による質問・相談テキスト**。

- 内容実測: 「アーリーステージの製品で X（旧Twitter）運用を始めたが、公式アカウントのみだとフォロワーが増えにくい。ファウンダーの個人アカウントと公式アカウントの2本運用にすべきか？どのようなコンテンツを投稿すべきか？」という問いかけ。
- スコア・コメント数実測: **3 points / 0 comments**（Algolia API `hit.points=3`, `hit.num_comments=0` で実測確認）。
- HN 上で議論すら盛り上がっておらず、コメントによる知見やツールの紹介・プロンプト・データセット等の提供も皆無。

## 自動化キーワード判定
Hunter フラグ「自動化キーワード含有: あり」= **誤検出**。
本文中の「App Store / X / build in public / engagement / followers」等の単語が機械的に引っかかったものであり、Kensho が自動化・スクレイピング・収益化できる機能やツール、データの記述は存在しない。
スキルの誤検出除外パターン「起業家の随想・悩み相談、CtoA/API/サービスなし」に該当。

## 3点評価（Kensho 非API収益モデル）
### 1) プロトタイプ — 不成立
- Kensho の核（スクレイピング + 集約 + LLM要約）を適用するデータもサービスも存在しない。
- 質問投稿本文のみ（約1,800文字の英文テキスト）であり、未取得データ・独占的価値は皆無。

### 2) ローンチ手順 — 不成立
- Kensho の配置経路（データAPI / 自動化 / 自前FastAPI / Apify / RapidAPI）に乗る要素がない。
- 「起業家の随想・悩み相談」はスキル定義上の標準却下パターンに直接該当。

### 3) 集客 — 不成立
- HN スコア 3 pt / 0 comment で観客規模は皆無。
- 集客アセットや CtoA 導線として利用できる要素なし。

## 結論
本件は「Xアカウント運用設計に関する個人起業家の単なる質問投稿（スコア3/コメント0）」であり、Kensho の自動化収益商品（データ商品・スクレイピング代行・自動化ツール）へ転換できる要素が一切存在しない。

- 成立条件を満たさないため、プロトタイプ / ローンチ手順 / 集客の3点はいずれも**着手しない**（24h 内タスクは no-op 完了）。

## verification_evidence
検証コマンド（2026-09-26 実測, task t_b0e41cef）:
$ curl -s "https://hn.algolia.com/api/v1/search?query=Ask%20HN%3A%20Does%20a%20startup%20need%20both%20founder%20and%20company%20X%20accounts%3F&hitsPerPage=5"
{
  "hits": [
    {
      "author": "OnionLayers",
      "num_comments": 0,
      "objectID": "49837729",
      "points": 3,
      "story_id": 49837729,
      "title": "Ask HN: Does a startup need both founder and company X accounts?"
    }
  ]
}
$ curl -s "https://hacker-news.firebaseio.com/v0/item/49837729.json"
{
  "by": "OnionLayers",
  "id": 49837729,
  "score": 3,
  "time": 1790289576,
  "title": "Ask HN: Does a startup need both founder and company X accounts?",
  "type": "story"
}
$ grep -c "t_b0e41cef" 2026-09-26-t_b0e41cef-askhn-x-accounts-eval.md
2
