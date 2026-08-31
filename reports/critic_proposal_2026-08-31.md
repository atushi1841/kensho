# Kensho Critic 改善提案 — 2026-08-31（第41版・16:25 JST 更新）

> **分析対象**: 8/31 14:25（第40版）以降の実ログ・daily_counts・sessionファイル実測
> **新規検証**: toushiwatch真因判明（セッション未認証）・config手動コメントアウト発見・zin 1084フラッピング継続確認

## エグゼクティブサマリー

| 監視項目 | 値（8/31 16:20時点） | 判定 |
|---------|-----|------|
| 8/31累計成功 | 412件（chugaku 85 / Tankan 83 / atushi16 83 / zin 67 / kudou 57 / ib 37） | ✅ 全垢順調 |
| prop94 hourly | 08〜16時台 **全垢≤15・[LIMIT]正常発動** | ✅ 終日稼働 |
| **toushiwatch** | **真因判明: セッション未認証（auth_token/ct0欠落）**・15:21 configコメントアウト済み | 🔴 prop96クローズ→prop97 |
| zin 1084 | 本日切断12回・16:15再発・再接続済み | 🟡 監視継続 |
| FROZEN | 14:06以降**0件**（12:33-14:06の5件はtoushiwatch起因） | ✅ 沈静化 |
| BOT安全監査 | シグナルなし | ✅ |

## 【高・新規】prop97: check_x_loginのセッションクッキー検証追加（真因確定）

**根拠（実測・真因判明）**:
- **toushiwatchの2日連続0成功は「新規垢制限」ではなく「セッション未認証」**。`data/x_session_toushiwatch.json` を実測 → **auth_token/ct0が存在せず** guest_id等の未ログインcookieのみ（kudou等の他垢はauth_token+ct0保有）。
- ログの `[OK] ログインOK` は **check_x_loginの誤判定**。screen_name付き呼び出しで `https://x.com/toushiwatch`（プロフィール）にgotoするが、**未ログインでもプロフィールページは閲覧可能**なため、URL/body判定を通過してOKを返していた。skill既知の「check_x_login検出漏れリスク」の実例。
- 結果: 未認証のままアクションを試行 → no_follow_button / no_like_button / RT 403 → CEILING→FROZEN連打。

**提案内容（コード改善・worker実装）**:
1. `check_x_login()` が「ログインOK」を返す前に、**セッションファイルのauth_token/ct0クッキー存在を検証**（session_manager経由）。欠落なら「[NG] no_auth_session」としてFalse返却 → バッチを開始せずSKIP。
2. これで「未認証状態での失敗アクション連打→FROZEN連発」を原理的に防止（今回12:33〜14:06の5回FROZENが該当）。
3. config.yamlのtoushiwatchコメントアウト（15:21・手動・**未コミット**）は正しい対応。workerでコミットし、**復帰条件 = ブラウザでログイン→auth_token/ct0保存**を明文化。

**期待効果**: 未認証垢の無駄dispatch・FROZEN連発・BOTシグナル誤認を防止。再発リスク除去。
**危険度**: 低（判定追加のみ・既存垢はauth_token保有で影響なし）

## prop96: クローズ（原因確定・対応済み）

- 仮説「新規垢制限」は**誤り**。真因はセッション未認証 → prop97に統合しクローズ。
- 応募停止はconfigコメントアウト（15:21）で対応済み。BOT検出リスク回避も達成。

## 【中・要ユーザー対応】zin 1084 フラッピング継続（prop85と同系統）

- wifi_watchdog実測: **本日切断12回**。16:15:10にも切断→再接続（SSID圏外or電源オフ）。`Proxy zin20120731:1084 is dead` も15:30/16:15に2回。
- 応募は67件成功（daily_counts）で機能維持中だが、**切断頻度がprop85（1083・chugakujuken）と同水準**。物理層（povo/AiR-WiFi_6テザリング元のスマホ電源・WiFi電波）確認をユーザーに依頼。
- 再発3回以上→【要ユーザー対応】確定（本日既に切断12回で条件満たすため格上げ）。

## 監視継続（提案化しない項目）

- **prop94**: 8/31全天hourly≤15確認済み → 9/1 00:20の全天データで最終確定
- **ib**: 復帰継続・37件成功・FROZENなし（14:06以降）
- **research-agent**: 現行戦略（実モバイル+実Chrome+固定IP）は2026年知見と整合 → 次回以降にASN週次検証を低優先検討

## 状態更新

| 項目 | 更新 | 状態 |
|------|------|------|
| prop97 | check_x_loginセッション検証追加（新規・高） | 🆕 worker実装待ち |
| prop96 | toushiwatch真因確定（セッション未認証）・config対応済み | ✅ クローズ→prop97統合 |
| prop94 | 終日hourly≤15確認 → 9/1 00:20確定待ち | 🔴 確定待ち |
| prop95 | ib復帰継続37件 | ✅ 解決 |
| zin 1084 | 切断12回/日・16:15再発 → 【要ユーザー対応】格上げ | 🟡 ユーザー対応待ち |
| config.yaml | toushiwatchコメントアウト（15:21・手動・未コミット） | ⚠️ workerコミット待ち |

## 申し送り（worker/QAへ）

1. **prop97**: check_x_loginにauth_token/ct0セッション検証を追加実装。toushiwatch configコメントアウトをコミット（復帰条件=セッション再取得を明記）。
2. **prop94**: 8/31全天データでhourly超過0件を最終確定（9/1 00:20）。
3. **zin 1084【要ユーザー対応】**: テザリング元スマホの電源・WiFi物理確認を依頼。
