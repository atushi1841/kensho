# critic_proposal_2026-09-10-v90 [ready→running]

## 提案: Apify Store公開インデックス欠落の解消（収益$0の構造的真因）

- タスク: t_443551e0（assignee=kensho-revenue-worker、19:40にdispatcherがclaim済・running）
- 優先度: **高**（応募停止級=収益が完全停止中、かつ自動復旧不能=手動提出が要る可能性）

## エビデンス（2026-09-10 18:30-19:10 実測）

1. `GET /v2/store?username=fruitful_quintessence`（無認証）→ `total=72, count=5, items=[]`
   対照 `username=compass` → `total=5, count=5, items=5件`。**total/countはあるのにitemsだけ空**＝一般ユーザーのStore一覧・検索から全アクターが完全フィルタされている。
2. 同一paramsのA/B（token有無）: `search=japan camera` → 無認証 items=42/my=0、認証 items=50/my=8。`surugaya` → 無認証 my=0、認証 my=4。**自分のトークンで見た時だけ自アクターが出現**＝インデックスは存在するが公開面に出ていない。
3. `isPublic=true`（25本全・API実測）は「誰でも実行可」の意味であり、**Store公開（Store提出・審査通過）とは別物**だと確認。store系の状態フィールドは actor detail のどこにも無し（`store/publish/monetiz*` キー検索で0ヒット）＝提出状態はWeb UI側。
4. 需要側の裏付け: bookmarks=0/72、flagship の publicActorRunStats30d SUCCEEDED=29 だが runs API の直近9件は**全て owner userId**（自家cron）。外部利用者=0 の測定は正しい。
5. メタ教訓: この items=0 挙動は9/8に観測済み（memory「watch scriptはcount読む」）なのに quirk 扱いで放置。**countとitems不一致=データ欠落サイン**は即提案化する。

## 実装内容（worker）

1. flagship 1本 `japan-used-camera-market-scraper` のApify Storeページ/ダッシュボードを Windows Chrome CDP 9222（`/mnt/c/temp/gumroad_update_cdp.js` 方式踏襲）で開き、"Submit to Apify Store" の状態確認→提出実行
2. API側に公開状態/提出エンドポイントが無いか最終確認（あれば25本へバッチ展開）
3. 審査制なら「提出完了・審査中」をレポート化、UI操作が必須なら【要ユーザー対応】でblocked化

## Verifiability

- 成功指標: 無認証 `store?username=fruitful_quintessence` の `items` 長 ≥ 1
- 検証コマンド: `curl -s 'https://api.apify.com/v2/store?limit=5&username=fruitful_quintessence' | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["data"]["items"]))'` → 0以外
- 失敗時代替案: 提出不可/審査待ちなら外部導線を devto 9/14（t_4e88dfeb）・Reddit告知（t_822876d6）へ集約し、Store側はユーザー判断へエスカレーション

## 効果見込み

Storeインデックス入り＝Apify検索トラフィック（月間数千query先）に初露出。25本PPE×$0.002/run、9/11統合判定（t_98334cc7）で external_users ≥ 1 が確認目標。
