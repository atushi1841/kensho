# critic v74（2026-09-09 16:4x）— hunterスクリプトdrift修正提案

## トリアージ結果（priority=backlog_reduction→完了）
- ready 22件（全て9/9 16:04、kensho-non-api-revenue-hunter一括生成）→ **22件全abandon+archive**
  - 21件はHN/PHの「Show HN」系記事で「自動化キーワード含有: なし」= worker実装対象でなく工数対収益が構造的に不一致
  - 1件（t_e91be184 Diiverge）は他社ローンチ製品そのもので評価不能
- トリアージ後: ready=0、score 65→85、priority=new_proposalsへ移行確認済
- 副作用: `hermes kanban comment` の日本語本文がtirithセキュリティスキャン（Confusable Unicode）で保留された → ASCII本文で再実行して解決。**教訓: kanban書込み本文は全角・日本語を避けるかASCII化**

## 提案（高優先・再発型）t_e971e85a
**root cause**: cron実行実体 = `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-non-api-revenue-hunter.py`（649行）に v58品質ゲート（quality_gate / MAX_KANBAN_PER_RUN=3 / has_monetization_signal）が**不在**。repo側（752行）には実装済み。プロファイルコピー同期漏れで、9/6のce22c907d66d drift（v30教訓「Verify 04:00 run success next tick」が未完了のまま残っていた）と同型**2度目の再発**。

対策2層:
1. repo版→profile版 md5一致コピー（バックアップ付き）
2. cron参照スクリプトのrepo/profile md5差を監視するdriftチェック恒久追加（kensho-ready-watchdog 8d22d346627b か kanban-hn-cleanup-daily 0775e27f5e7e に相乗り）

成功指標: 9/10 16:00 run後の当日作成<=3件 / md5sum一致 / driftチェックがWARN・OK出力1回以上
検証: `md5sum /mnt/d/Project2/kensho/kensho-non-api-revenue-hunter.py /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-non-api-revenue-hunter.py`
代替: 同期後も>3件ならhunter cron 458eacc3c96c pause→【要ユーザー対応】

## 効果実測（前回提案 v73）
- GitHub 404: 自己回復（QA実測 ls-remote rc=0、bundle+cron 05:30二重バックアップ確立）→ v72「要ユーザー対応12h+エスカレーション」ルールが機能し代替案が2tick以内に実行された ✅
- t_51542f18 frontier_k: run321正常稼働中（wip 2件のうちの1件、完了待ち監視はQAへ申し送り済み）

## 監視
- in_progress 2件（t_51542f18 frontier_k + 1件）— score -10要因。次tickで完了状況確認
- dirty=Y（ワーキングツリー未コミット）継続 — QA v73が「dirty=N定着」と報告していたがmonitor署名はdirty=Y。次tickで再確認
