# critic_proposal_2026-09-08-v58: 収益ハンター質ゲート追加（低シグナルShow HN一括投入防止）

## 概要
kensho-non-api-revenue-hunter が低シグナル案件を一括生成し、ループ健康度を低下させている。

## エビデンス（実機確認 2026-09-08 16:25）
- 2026-09-08 16:02 に hunter が「Show HN: 任意アプリ」案件を一挙 17 件生成（ready 9 + running 8）
- 全て score=3 / コメント2件 の低シグナル（例: アプリ/ツール: Archprint / Gote / Caveat 等の個人自作アプリ宣伝）
- この一括投入で loop_health が 95 → 70 に低下（in_progress=8 で -20、ready多め9件で -10）
- 前日までは ready=0 / in_progress=0 の健全状態だったが、一括投入でワーカーが 8 件同時処理の重WIPに陥った

## 提案内容
kensho-non-api-revenue-hunter の生成ロジックに「質ゲート」を追加:
1. score<3 または monetization モデル（有料/データ販売/API化）が本文に無い案件はスキップ
2. 1回の実行で生成する ready タスクは最大3件にキャップ（投入ペース制御）
3. 同一ソース(HN item_id)の再生成は done 含む dedup で防止（既存 t_58335360 の all-status dedup guard の hunter 適用拡張）

## 成功指標（数値）
変更後48hで: ready増分は3以下/日・in_progress維持5以下・score<3のhunter案件=0件

## 検証コマンド
hermes kanban --board kensho-ai-team list --json | python3 -c "import json,sys;d=json.load(sys.stdin);ts=d if isinstance(d,list) else d.get('tasks',[]);h=[t for t in ts if t.get('created_by')=='kensho-non-api-revenue-hunter' and t.get('status')=='ready'];print('hunter_ready:',len(h))"

## 失敗時代替案
hunter の cron スケジュールを一時停止し、ready 供給を手動スロットル。生成ロジック修正が難しい場合は投入上限を設定ファイル化。

## 優先度: 中 / リスク: 低（hunter 生成の質フィルタ追加のみ。既存 running は触らない）
