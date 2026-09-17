# 週次マーケットレポート有料購読 — 実装前検証結果 (t_1b2ecfa1)

作成: 2026-09-18 / kensho-revenue-worker

## 検証サマリ

このタスク（アイデア4: 週次マーケットレポート有料購読）の実装計画が依存する前提のうち、
**3つが実測で成立していない**ことを確認。実装コード（reports/weekly_market_report.py,
core/notifier.py の email送信追加, cronスケジュール）を書くよりも先にブロッカーを報告し、
ユーザー判断を仰ぐべきタスクと判定。

## 検証項目（git status は他タスクの未コミット変更14件で汚れているが本件の変更は無し）

### 1. 🔴 GUMROAD_TOKEN 未設定（検証コマンドが実行不能）
- `~/.env` 実測: 定義済みキーは `DEEPSEEK_API_KEY / DEVTO_API_KEY / APIFY_TOKEN_DEFAULT` のみ。
  GUMROAD_TOKEN は不在。
- `data/gumroad_state.json`: login_ok=false, sales=0, dashboard_url がログイン遷移。
- タスク本文の検証コマンド
  `curl -s https://api.gumroad.com/v2/products?access_token=$GUMROAD_TOKEN | jq ... .sales`
  は token 不在のため実行不能。
- これは t_55210446（Gumroad販売ページ作成）と同じ原因で2日間 blocked 継続中のブロッカー。
  ユーザーによる Gumroad APIトークン発行が必須。

### 2. 🔴 email配信基盤は「既存」でない（前提の実装計画が崩れる）
- `kensho/core/notifier.py`: Windowsトースト / Discord webhook / Linuxファイルログ のみ。
  **email/SMTP送信機能は無い**。
- config.yaml: `notify.discord_webhook=""`、`telegram.enabled=false`。
- リポジトリ全体で smtplib / Resend / Mailgun / SendGrid / Buttondown / Substack の
  送信コード・設定は皆無。
- 調査レポート research-20260917.md は「メール配信基盤は既に構築済（notifier）」と記載
  しているが、これは**実測と矛盾**（notifier.py に email が無い）。

### 3. 🔴 「今週の日本コレクtibles市場動向」を生成できるデータが無い
- `data/collected.json` は **懸賞キャンペーン（応募）データ**（prize_items=Amazonギフト券 /
  winner_count / deadline / x_url 等, 1092件）。
- Kensho のコレクションは提供プレゼント懸賞の応募管理であり、
  「日本コレクtibles市場動向（価格・流通・トレンド）」とはデータ種別が異なる。
- 懸賞データをコレクタブル市場レポートとして要約するのは内容のすり替えになる。

### 4. 🟡 cronのweekly_reportジョブは存在しない
- `~/.hermes/**/cron.json` を走査: "weekly / market / report / news / subscri" に一致する
  ジョブは存在しない。「ロールバック: cronからweekly_reportジョブを削除」の
  対象ジョブそのものが無い。

## 結論・推奨

有料週次配信の**開始**には、ユーザーの以下の判断／提供が必須（エージェント単独では解決不能）：

1. **販売／配信基盤の選定** — Buttondown / Substack / Gumroad のうちどれを使うか
   （現状はGumroad希望だがtoken無し。配信手段はemail基盤が無いため別途要構築or外部サービス）。
2. **GUMROAD_TOKEN の発行**（t_55210446 と同じ）→ .env に設定。
3. **レポートのデータ源の現実化** — 懸賞応募データを「市場動向」として出すのか、
   それとも別の日本市場データ（Apify検索API等）を購読者向けに回すのかの決定。

上記が決まったら、改めて実装タスク（report生成+配信スケジュール）を切るのが妥当。
現状のまま報告ファイルを生成しても、検証コマンドが実行できず採用可否が判定できない。
