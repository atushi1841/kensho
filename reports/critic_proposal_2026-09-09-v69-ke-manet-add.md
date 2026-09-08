# critic v69提案 — ke-ma.net 第5収集ソース追加 (2026-09-09)

[status]: open
[kanban]: t_436ed21b (ready, kensho-worker)
[優先度]: 中
[リスク]: 低

## エビデンス
- **research agent 9/7調査**: ke-ma.net(懸賞マニア)追加が最優先と明記。Xキャンペーン専用カテゴリ+即時抽選/大量当選カテゴリが構造化、スクレイピング適性高。
- **今回の実地検証**: WSL curl `https://ke-ma.net/` → HTTP 200・171KB取得。記事リンク87件確認。期限日付表記(`09月21日`等)約30件検出。X公式(x.com/ke_ma_net)存在。Webアクセス可能であることを実測確認。

## 狙い
既存4ソース(knshow/ken-kaku/kenshou.club/cp.meikan)に追加し、収集母集団を拡大→応募件数増→当選確率向上。

## スコープ
収集パイプラインのみ（応募ロジックは非変更）。collector.pyにke-ma.net記事URL(/105836/等)パーサー追加、data/ke_ma_*.json保存。

## Verifiability
- 成功指標: 次回収集でdata/ke_ma_*.json生成・エントリ数>0
- 検証コマンド: `python3 -c "import json,glob; d=json.load(open(glob.glob('data/ke_ma_*.json')[0])); print('entries', len(d if isinstance(d,list) else d))"`
- 代替案: Cloudflare等ブロック時はabandoned化→別ソース検討

## 二重処理防止
idempotency-key: critic-20260909-v69-KEMA（同一キーならhermesが既存を返す）
