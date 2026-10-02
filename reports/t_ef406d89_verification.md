# t_ef406d89 Apify Figure Price Actor 公開化修正 — 検証証跡

実施: kensho-sweeps / 2026-09-28 20:40 JST
対象: Apify actor `japan-anime-figure-price-data` (ID: DKzufUSvmuXNKHeYx, owner: fruitful_quintessence)

## 真因

これまでの診断「APIFY_TOKEN が読み取り専用で isPublic は 403 → ユーザーの Console 手動操作が必要」は**誤り**。

真因は `defaultRunOptions.build` がスタックした旧ビルド **0.1.93** に固定されていたこと。
0.1.93 には input/output schema が無く、Apify は schema の無いビルドの公開を拒否するため
`PUT {"isPublic": true}` が 403 を返していた。トークンの権限問題ではなかった。

## 実施コマンド（実測出力付き）

1. 既定ビルドを最新 SUCCEEDED に更新

   PUT /v2/acts/DKzufUSvmuXNKHeYx
   {"defaultRunOptions": {"build": "0.1.174", "timeoutSecs": 300, "memoryMbytes": 1024}}
   → HTTP 200
   read-back: defaultRunOptions = {"build": "0.1.174", "timeoutSecs": 300, "memoryMbytes": 1024}
   taggedBuilds.latest = {"buildNumber": "0.1.174", "finishedAt": "2026-09-28T10:47:59.598Z"}

2. 公開化

   PUT /v2/acts/DKzufUSvmuXNKHeYx {"isPublic": true}
   → HTTP 200
   read-back: isPublic = True

## verification_evidence

```
$ GET /v2/acts/DKzufUSvmuXNKHeYx | jq '{isPublic, defaultRunOptions.build}'
{
  "isPublic": true,
  "defaultRunOptions": {"build": "0.1.174", "timeoutSecs": 300, "memoryMbytes": 1024}
}
```

判定: **公開化 成立**（isPublic=true を API の read-back で確認）。
残作業: `description` が過去の書き込みテスト残骸 `TEST-WRITE-OK` のまま。Store 用説明文の整備は t_a57c6538 に引き継ぎ済み（コメント1687）。
