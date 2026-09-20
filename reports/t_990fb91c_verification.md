# 検証レポート: 中古カメラ差益アラート・7日間連続監視実行 (t_990fb91c)

タスク: t_990fb91c（承認タスクID）
job: nightly-worker

## 受け入れ条件と対応
- 既存監視スクリプト scripts/camera_monitor.py は変更せず日次ラッパーを新設 → 実装
- 7d_repro_audit.csv にZ9/Z8の日次相場差を蓄積 → 初期化+ラッパーで毎日追記
- Z9/Z8のみ抽出・1日1回・Bot回避 → 実装
- 最終日集計+月額980円妥当性結論 → 子タスク(t_990fb91c-child)へ委譲（7日後）

## verification_evidence
- `bash scripts/camera_monitor_7d_daily.sh` (TODAY=20260920) => exit 0, ログ
  `reports/camera_monitor_7d_daily_20260920.log: "SKIP: audit already has 20260920"`（冪等性確認）
- `python3 -m scripts.camera_monitor`（既存・t_0b0d1647実績）=> data/camera_monitor/
  run_summary_20260920.json に models=30, Nikon Z9 median_diff_pct=8.1/max=27.0,
  Nikon Z8 median=-15.9/max=10.7 を実測
- `hermes kanban --board kensho-ai-team show t_990fb91c`（claim所定コマンド）=> Claimed t_990fb91c
- `crontab -l | grep camera_monitor_7d_daily` => `30 13 * * * .../camera_monitor_7d_daily.sh`（1日1回登録）
- `cat data/camera_monitor/7d_repro_audit.csv` => 見出し+`20260920,Nikon Z8,...,-15.9,10.7`+`20260920,Nikon Z9,...,8.1,27.0`

## 実測エビデンス
初回Z9/Z8実測（9/20）: 駿河屋×Yahoo差益候補
- Nikon Z9: median 8.1% / max 27.0%（67,530円差の候補あり）
- Nikon Z8: median -15.9% / max 10.7%（34万円台の仕入れ候補あり）
→ 差益機会は実在。7日間の継続計測で再現性を判定。
