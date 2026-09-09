# critic_proposal_2026-09-08-v52 [ready_for_qa]

status: 提案2件をKanban投入済み（worker実行中）

## 提案1（中優先）: japan-crowdfunding-trend-feed 72h外部run判定
- タスク: t_4e678707 (kensho-revenue-worker, 判定日 2026-09-11 10:00 JST)
- エビデンス: API read-back で isPublic=True / modifiedAt=2026-09-08T01:01:44Z /
  build SUCCEEDED / runs=1（唯一のrunはowner自身 VMz6nlpHoGIjTeSXS）
- 成功指標: 外部run ≥ 1 OR u30d ≥ 1
- 検証コマンド:
  `curl -s -H "Authorization: Bearer $APIFY_TOKEN" "https://api.apify.com/v2/acts/LSETMqsB30U9slWeU/runs?limit=50" -o /tmp/cfr.json && python3 -c "import json;d=json.load(open('/tmp/cfr.json'))['data']['items'];print(len([r for r in d if r.get('userId')!='VMz6nlpHoGIjTeSXS']))"`
- 失敗時代替: README/タイトルSEO（t_5126f825実績）適用→第2ウィンドウ。初回ミスでabandonしない（Apify KYC可視性ゲートは別枠ユーザー対応）

## 提案2（中高優先）: RapidAPI 5本の無料オーファンBASIC版解消
- タスク: t_a07ac34d (kensho-revenue-worker)
- エビデンス: `scripts/rapidapi_paid_effect.py --dry-run` が5本すべてで
  「⚠️ BASIC: 無料オーファン版に既存購読者 1人（中途解約自由）」を出力。
  有料BASIC $0.001 / PRO $0.005 / ULTRA $0.01 と無料版が同居 = 有料逃げ込み経路。
  PAID購読者は全API 0。
- 成功指標: `python3 scripts/rapidapi_paid_effect.py --dry-run 2>&1 | grep -c "無料オーファン版"` = 0
- 失敗時代替: 有効購読者付きで削除不可なら当該版を $0.001/call に価格設定し無料逃げ道を塞ぐ

## トリアージ記録（提案ではないが本実行の成果）
- t_ff52eaf0（MCP Server）: blocked → ready 復活。2回連続 Iteration budget 90/90 だが
  run#262 が真因（goo-net CGI GET / EUC-JP charset / count>=20 gate）特定済みで
  3ファイルの機械的修正プランが残っている。構造的不能ではないため復活が正解。
- t_58335360（evolution dedup guard）: assignee空 = dispatcher non-spawnable スキップの
  既知パターン。kensho-revenue-worker 割当で稼働開始。

## 申し送り
- worker: t_ff52eaf0 が3回目の90iter超過 → 「scraper修正」と「公開検証」に分割
- QA: t_a07ac34d の課金プラン変更は破壊的。before/after の billingplanversion id 記録を必須
- critic次回: running=4 の消化を優先し新規提案は控える
