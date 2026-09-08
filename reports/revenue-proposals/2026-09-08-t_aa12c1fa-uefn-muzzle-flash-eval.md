# 検証記録: UEFN Muzzle Flash VFX チュートリアル 非API収益評価（t_aa12c1fa）

- 対象: https://qiita.com/RealTimeVFX/items/257d38e40a7e81239c4e（Qiita 週間新着・自動化の文脈で検出）
- 判断: 却下（実装対象外）— 純然たる UEFN/Fortnite Niagara VFX 作成チュートリアル記事で、自動化・データ・API・ダウンロード素材・サービス導線が一切なし。収益モデルゼロ、既存 Kensho scraping/LLM 資産で再現不可能、観客ゼロ。
- 検出カテゴリ「自動化サービス受託/教材」は誤ラベル: 本文に自動化キーワード無し、ゲームVFX手順書に過ぎない。
- 詳細は添付 evaluation_report.md。

## 3点評価

### 1) プロトタイプ — 不可
- 本文は「Niagara でクロスプレーン火炎メッシュ + スパーク/グロー、ライフルバレルへのバインド、UE6用最適化」のハウツー説明のみ。LLM要約・スクレイピングの対象となる公開データDS/API/RSS 皆無。
- 実装物は Unreal Engine 5 Niagara のVFXアセットで、Kensho の Python scraping + LLM 資産とはゼロ重複。素材ダウンロードも販売導線も無い。

### 2) ローンチ手順 — 不可
- Kensho の配置経路（データAPI / 自動化 / 自前 FastAPI / Apify/RapidAPI）のいずれにも載らない。UEFN ゲーム制作という継続的スキル職で、受動収益ではない。

### 3) 集客 — 不可
- 投稿 0 いいね / 0 コメント / 当日投稿、著者 RealTimeVFX のフォロワー 0。観客規模ゼロ。原サイトの注目度ゼロ。

## verification_evidence

```
$ curl -s -w "%{http_code}\n" -o /tmp/qitem.json "https://qiita.com/api/v2/items/257d38e40a7e81239c4e"
  200
$ grep -oE '"(title|likes_count|comments_count|created_at|private)":("[^"]*"|[0-9]+|true|false)' /tmp/qitem.json
  "title":"UEFN VFX Tutorial | Make MUZZLE FLASH (UE6 Ready) 💥"
  "likes_count":0
  "comments_count":0
  "created_at":"2026-09-08T15:26:13+09:00"
  "private":false
$ curl -s "https://qiita.com/api/v2/users/RealTimeVFX" | grep -oE '"(id|followers_count|organization)":("[^"]*"|[0-9]+|null)'
  "id":"RealTimeVFX"  "followers_count":0  "organization":null
$ curl -sL -o /dev/null -w "%{http_code}\n" "https://qiita.com/RealTimeVFX/items/257d38e40a7e81239c4e"
  200
```

冒頭から証跡セクション末尾まで言及 task_id は t_aa12c1fa（本タスク）のみ。
