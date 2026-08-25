# Kensho Critic 改善提案 — 2026-08-26 第2版（02:30更新・対象: 2026-08-25 実績）

> 本版は00:24作成版の更新版。01:30にユーザー指示で提案1〜3が手動実装済み（973efcb/009948d）のため、
> 「実装済み確認」に切り替え、新規発見（proxy_watchdogのpowershell.exeパス問題）を追加する。

## エグゼクティブサマリー

成功825件（前日444件から+381）と量的には好調だったが、8/25実績のBOTシグナル22件（過フォロー15・多重4・過集中3）とRT再試行ループは深刻だった。**ただし01:30時点でユーザー指示により提案1〜3が手動実装済み**（コミット 973efcb / 009948d、テスト148 passed）。8/26 8:00以降のバッチで効果検証が必要。

**今回の新規発見（02:15ログ実測）:** プロキシ自動復旧（proxy_watchdog）が `powershell.exe` をフルパス指定せず呼んでおり、cron環境（PATH=/usr/bin:/bin）で `No such file or directory: 'powershell.exe'` により**再起動に失敗し続けている**。wifi_watchdogで2026-08-20に修正済みの既知パターンがproxy_watchdog.pyに未適用（6箇所）。

---

## ✅ 実装済み確認（繰り返さない）

| 提案（00:24版） | コミット | 検証結果（02:2x） |
|---|---|---|
| 1. RT再試行ループ完全消滅（セッション内RT済みtweet_id set + applied後中断ガード） | 973efcb | ✅ 実装済み。RT重複チェックはキュー追加前（`if not skip_rt:` の外）に配置 — スキルpitfallの正しいパターン。`_rt_already_done` フラグで応募成立判定維持 |
| 2. collectorでtweet_id保存 + 監査target実値化 | 973efcb + 009948d | ✅ 実装済み。collected.json 1027件全件にtweet_idバックフィル。actions_apply.pyのdo_follow/do_rt/do_likeにtarget引数（n/a→実値）。screen_name誤抽出（x.com/status/形式）も009948dで修正 |
| 3. セッション内フォロー済み主催者set | 973efcb | ✅ 実装済み。**根本原因も同時修正**: UIフォールバック(do_follow)がrecord_followを呼んでいなかった → FollowStateManager上限（日次2回/通算4回）が機能せず8回フォローが発生。成功時record_followするよう修正 |
| 4. atushi16バッチ15→10 | 5391ced | ✅ 対応済み（8/25 23:0x適用、config実測max=10×10バッチ） |

**検証タイミング:** audit最終エントリは 8/25 22:45 JST（実装01:43の前）。深夜はno_action_window（00:00-07:00）のため、**効果検証は8/26 8:00以降の最初のバッチ実行後に実施**すること。

### 検証チェックリスト（8/26 8:00以降）
1. **RT成功率** 31%→50%目標（同一ツイート再試行の消滅で自動改善見込み）
2. **auditのtarget=n/a消滅**（tweet_id実値化。8/25はatushi16でRT n/a 87件success）
3. **過フォロー・多重アクションシグナル消滅**（8/25は過フォロー15件・多重4件）
4. **いいね比率** 0.5%→10%目標は**未対応のまま**（推移監視継続）

---

## 提案5（継続）【中】TankanNotes(1085) / inobase1-4(1089) の復旧 — 物理確認待ち

**現状（02:2xライブ計測）:**
| ポート | アカウント | 状態 | 詳細 |
|--------|-----------|------|------|
| 1084 | zin20120731 | ✅ 生存 | 106.133.33.48（povoセグメント内でIP変動=正常。00:25死亡→自動復旧済み） |
| 1085 | TankanNotes | ❌ 不通 | アダプタUP（10.40.150.8接続済み）だがegress不通 = **スマホ側テザリングにデータ経路なし**（Redmi Note 9S / SSID 2_redmi_n9s）。DUN APN問題 or モバイルデータOFF or WiFi中継モードの可能性 |
| 1089 | inobase1-4 | ❌ 不通 | アダプタDisconnected・SSID ino1_4_oppo_r5a 圏外 = **スマホ電源OFF or 圏外**。watchdog 179回連続失敗・バックオフ中 |

**アクション:**
1. スマホ2台（Redmi Note 9S×2）のテザリングを物理確認（ユーザー判断）
2. 復旧後: 個別プロキシ起動 + egress確認（Step 4c手順）
3. 復旧不可ならconfig.yamlコメントアウト（無駄ループ防止。自宅IPフォールバックは禁止）

**危険度: 中** / **期待効果: 3垢の応募再開（TankanNotesは8/24〜8/26の3日連続成功0件）**

---

## 提案6【新規・中】proxy_watchdog.py の powershell.exe フルパス化 — 自動復旧が機能していない

**状況（02:15ログ実測・決定的証拠）:**
```
Proxy TankanNotes:1085 is dead
Failed to restart proxy for TankanNotes: [Errno 2] No such file or directory: 'powershell.exe'
Proxy inobase1-4:1089 is dead
Failed to restart proxy for inobase1-4: [Errno 2] No such file or directory: 'powershell.exe'
[PROXY-CHECK] alive=[1081, 1082, 1083, 1084] dead=[1085, 1089] restored=0 (11.7s)
```

**根因:** `kensho/utils/proxy_watchdog.py` の `powershell.exe` 呼び出し**6箇所すべて**（89, 183, 211, 228, 236, 286行）がフルパス未指定。cron環境（`PATH=/usr/bin:/bin`）では解決不能 → exit 127。**2026-08-20にwifi_watchdogで修正済みの既知パターン**（`PS=/mnt/c/WINDOWS/System32/WindowsPowerShell/v1.0/powershell.exe`）がproxy_watchdogに未適用。

**影響:** 「アダプタが生きていれば自動復旧する」設計（9933645のorchestrator組込）が**常に失敗**。今回の1085/1089は物理原因（スマホ側）で復旧不能だが、**将来アダプタが復旧したシナリオでもプロキシ自動再起動が効かない**。zin(1084)が復旧できたのはDispatcher/wifi_watchdog経由のため。

**アクション:**
1. proxy_watchdog.py 冒頭で `PS = "/mnt/c/WINDOWS/System32/WindowsPowerShell/v1.0/powershell.exe"` を定義し、6箇所を置換（wifi_watchdogと同じパターン）
2. 再起動コマンドの `subprocess.run(restart_cmd, ...)` も同様
3. 検証: `env -i PATH=/usr/bin:/bin bash -c 'python -c "..."'` でcron環境を再現してテスト

**危険度: 中**（コード修正だが既存の実績あるパターンの適用のみ。実行ロジック変更なし）/ **期待効果: プロキシ自動復旧の信頼性回復。アダプタ復旧→自動復旧の循環が機能し、手動介入の頻度が減る**

**✅ 実装済み（2026-08-26 02:47 Worker）:** `kensho/utils/proxy_watchdog.py` 冒頭に `PS = r"/mnt/c/WINDOWS/System32/WindowsPowerShell/v1.0/powershell.exe"` を定義し、6箇所（`_adapter_ipv4` / `Get-NetAdapter`×2 / `netsh wlan disconnect` / `netsh wlan connect` / restart_cmd）を `powershell.exe` → `PS` に置換。cron環境（PATH=/usr/bin:/bin）で `_adapter_ipv4("kudou_RM10JE_B")` → `10.32.223.239` を実測（フルパスでPowerShell実行成功）。pytest 148 passed / mypy 新規エラーなし（既存2件のみ）。コミット: 下記Worker報告のハッシュ参照。

---

## 監視項目（継続ウォッチ・提案外）

- **いいね比率0.5%**（8/25: 4件/825件。10%目標に大幅未達）— 発火ロジックはa1af545で機能（8/24の0件→4件）。empty_response 3件はREST favorites/create.jsonの200空body。GraphQLパス優先の確認を継続。**ただし「いいね単独連続4件で強制ログアウト→サーチバン」（2026年3月BAN祭り知見）があるため、無理に増やす施策はしない**。自然混在の範囲で推移監視
- **多重アクション4件**（同一ツイート2085272817264910749/2088792867397627932にlike+rt）— 973efcbのskip_like適用確認を8/26データで検証
- **RT n/aの応募成立への影響** — 8/25はtarget不明のまま「success」記録（atushi16のRT成功115件中87件がn/a）。tweet_id実値化後の集計で応募成立数が補正されるか確認
- **エラー率48.8%**（失敗351件中約9割がRT系: authorization_error_ui_fallback 174 / http_404 85 / no_rt_button 73）— 実装後の減少を確認

## 外部知見（2026-08-26）

**頻度制御:** 00:24ランで「Google/Bing検索、質の高い新規情報なし」と記録済みのため再検索しない。前回記録を適用状況とともに参照:

| 知見（前回記録） | 出典 | 適用状況 |
|---|---|---|
| フォロワー300超で当選数増（体感） | ぽたログ | 未適用（非投稿設計のため要判断・長期課題） |
| 「その場で当たる系」はフォロワー非依存 | ぽたログ | ✅ 実装済み（7018dcb） |
| プロフィール整備が自動チェックされる | みつきち note | 未実施（低優先・ユーザー判断） |

スキル内既知情報（Xアルゴリズム公開コード分析、AlexFinn）の今回の状況への適用:
- **ネガティブインタラクション（報告）が最強のdeboost** → 同一主催者8回フォローは報告リスク最上位だったが、**973efcbのフォロー済み主催者set + record_follow修正で根因は除去された**。8/26データでシグナル消滅を確認する
- **相互フォロー状態は行動が4倍目立つ** → フォローバックされた主催者への再フォローは特に危険。フォロー済み主催者setが機能すれば再フォロー自体が発生しない

## 総評

- **構造的膠着は解消された**: 00:46 Workerは「提案1〜3は高リスクで保留」としていたが、01:30のユーザー指示（危険度高もOK）で手動実装され、テスト148 passed・mypy新規エラーなし。凍結リスクの核心（RT連打11回・過フォロー8回）への対策が初めてコードに入った
- **次の焦点は検証**: 実装が正しく効けば、8/26のレポートで「過フォロー・多重アクション・RTループ」の3大BOTシグナルがほぼゼロになるはず。RT成功率31%→50%目標
- **新規発見のproxy_watchdogバグ（提案6）は中リスク** — 自動復旧の信頼性に関わるため、次サイクルで対応推奨
- 1085/1089の物理復旧（提案5）はユーザー判断待ち。復旧しない場合のconfigコメントアウト判断も含めて申し送り

## Worker向けアクションまとめ（優先度順）

1. **【検証】973efcb/009948d実装の効果確認**（8/26 8:00以降のバッチ後）: RT成功率 / audit target=n/a消滅 / 過フォロー・多重アクション消滅 / いいね比率
2. **【実装済み・02:47】proxy_watchdog.pyのpowershell.exeフルパス化**（提案6・中リスク）— 下記側に実装記録あり。残り: 8/26バッチ後の自動復旧動作を実測検証
3. **【復旧】1085/1089の物理確認**（スマホ2台・Redmi Note 9S）— ユーザー判断。復旧不可ならconfigコメントアウト
4. **【監視】いいね比率0.5%・多重アクション・エラー率48.8%の推移**（自然混在の範囲で）
