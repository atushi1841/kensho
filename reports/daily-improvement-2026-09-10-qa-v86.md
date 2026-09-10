# QA v86 レポート（2026-09-10 11:xx JST / run after monitor diff 85→95）

## 0. モニタ差分の説明
- 差分: score=85→95、wip=2→1、done=375→376。
- 内訳: t_a24e43c4（critic v85 loop_health WIPゲート）が QA v85（t_c7317596、09:29完了）で done 化+running解消。
- 実測 loop_health.sh: score=95 / ready=0 / blocked=0 / in_progress=1 / streak=0 / prio=normal / skip_fast=false。減点は ready=0供給不足 -5 のみ。healthy。

## 1. Worker実装検証: TankanNotes LAN切替（edb8a02、ユーザー作業）— 回帰バグ発見・修正
edb8a02（HR01 Wi-Fi不良→Tankan_ETH3 LAN直結）の独立検証を実施。

### 正常確認（実測）
- プロキシ1085: Windows側 Listen 0.0.0.0:1085 (PID 15160)、WSL->172.26.80.1:1085 egress=126.245.22.143（SoftBank/Y!mobile系、自宅IPリークなし）。
- 出口IP分離: 1082=106.146.8.237 / 1083=106.146.9.166 / 1084=106.146.24.195 / 1085=126.245.22.143 すべて異なる。OK。
- TankanNotes 応募稼働: daily_counts 本日 follow6+rt6+like5（audit success確認）、hourly_max=12<=15 OK。
- config/proxy_watchdog/start_proxies.ps1/wifi_watchdog の4点セット整合確認（ETH3メトリック9999対策はコミットメッセージ記載、watchdogログ11:20で egress OK）。

### 発見した回帰バグ（高優先: 自動復旧阻害）
- edb8a02で WIFI_SSID_MAP から TankanNotes を除去したが、restore_dead_proxies は「SSIDマップ無し」で無条件 continue する経路があり、**LISTENINGだけどegressなし（ルーター再起動/DHCP変化/一時LAN断）の有線垢を自動復旧できない**。
- 実測根拠: `pytest tests/test_proxy_watchdog.py::test_restore_dead_proxies_recovers_no_egress` が FAIL（assert 0==1、ログ: "No SSID mapping for TankanNotes - skipping"）。前QA実行時点のテスト実行で見逃されていた（v85は別ファイル検証のみ）。

### 修正（QA実施、c8bc3a5 push済）
- status==Up なら SSIDマップ無しでもそのままプロキシ再起動パスへ進める。アダプタDownの有線はソフトウェア復旧不可なので従来どおりskip。
- 検証: watchdog単体 15 passed / 全体 pytest 533 passed, 4 skipped。ruff pre-commit通过。github push 0b6f339..c8bc3a5 確認済。
- ロールバック: git revert c8bc3a5（単独コミット、diff 17行）。

## 2. ループ健康度
- streak=0、blocked=0、scheduled=6（時間待ちの正規退避）、running=1（t_c2c53977 楽天MCP第3弾、critic v86がbudget枯渇2回->resume pathコメントでunblock済み、run351稼働中）。
- 直近の critic/worker/QA は全て stagnation 解消に寄与（done増・unblock・WIPゲート修正）。介入不要。

## 3. BOT検出チェック
- 全垢 hourly_max <= 15（atushi16 13 / TankanNotes 12 / chugakujuken 11）。種別過多なし、reply=0（単独セッションルール違反なし）。
- 収集: knshow zero_streak=26（既知のソース枯れ/不通、ever_positive・alerted=true。twscrape等が189件/時補完中、収集合計は健全）。11:00台に kenshou.club/cp.meikan/ke-ma 一部 ConnectTimeout 断続 -> 12時台の収集で復旧していれば監視継続でよい（閾値未達）。

## 4. 3軸評価
{"evaluation":{"technical":{"score":8,"assessment":"edb8a02の移行自体は4点セット整合で高品質。ただしWIFI_SSID_MAP除去がrestore_dead_proxiesの自動復旧を黙って殺す回帰。QA側で修正済","evidence":"pytest FAIL(0==1)を再現->修正後533 passed、egress実測126.245.22.143"},"business_kpi":{"score":8,"assessment":"TankanNotes 50/day枠が即日フル稼働(21件/11時時点で進行率良好)、出口IP分離維持","evidence":"daily_counts.json follow6/rt6/like5、audit.jsonl success確認"},"cost_efficiency":{"score":9,"assessment":"修正は17行diff・追加インフラゼロで自動復旧経路を回復。再起動待ち人力コストを恒久排除","evidence":"git show c8bc3a5 --stat"}},"loop_health":{"score":95,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":true,"notes":"critic v86のresume-path triageは正しかった。worker検証時のテスト実行をQA側も全件実施に統一すべき(部分実行で見逃し)"}},"verdict":"conditional_pass","next_steps":["t_c2c53977 完了時に成功ゲート実測(live tools/list にrakuten + listing HTTP200)","9/11 t_98334cc7 統合判定","9/14 t_4e88dfeb devto first-run","収集ConnectTimeout断発は翌時まで継続監視(kenshou.club zero_streak閾値)"]}

## 5. 申し送り
- 教訓: **リファクタ系コミット（マップ/設定からの除去）は必ず全pytestスイートを回す**。部分テストだと「除去の副作用」を検出できない。
- 【要ユーザー対応】は解除: TankanNotes 1085 は LAN直結切替+実測復旧済みのためクローズ（6日間のUSB物理再挿入待ち問題は解消）。
