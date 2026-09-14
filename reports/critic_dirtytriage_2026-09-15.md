Kensho Critic 改善ノート — dirtyツリー一括適用トリアージ
日付: 2026-09-15 / 担当: kensho-critic / 対象タスク: t_fa161ec9
関連: revenue-worker run458 検知 / 親セッション telegram「AIチームの権限付与による働き改善」(2026-09-13)

================================================================
0. 結論（エグゼクティブサマリ）
================================================================
検知された「04:50:32 一括適用の未コミットコード5ファイル」は
「出所不明のゲート迂回・悪意ある適用」ではなく、9/13 23:08–23:27 に
kensho-sweeps サブエージェントが **ユーザー承認済み**(telegram)の
「anti-freeze 改善」として書き込んだ産物である。
04:50:32 の全ファイル同一 mtime は **pre-commit フックの stash/restore による
file mtime 再設定** であり、再適用ではない（証拠: pre-commit キャッシュに
patch1789415421-1701125 @ 2026-09-15 04:50:21 が存在 / git には未コミット）。

ただし内容に以下の欠陥・違反があるため、一部は還元/修正が必要:
  - proxy_watchdog.py: ハードルール「垢別SOCKS5 IP分離は絶対条件・変更禁止(2026-08-01)」
    に設計上正面衝突する自動ローテーションを追加（現在未呼出=dormant だが将来リスク）
  - config.yaml: 重複キー欠陥（kudou 配下に schedule: が2つ→後勝ちで kudou 本来時刻が
    chugakujuken 旧時刻に静的上書き）+ kudou/zin の wifi_profile 指定消失
  - applier.py / session_manager.py / gen_status_data.py: 承認済み健全化 → 維持

================================================================
1. 出所特定（実測エビデンス）
================================================================
* kensho-sweeps state.db セッション 20260913_230817_427f48 (source=subagent,
  parent=20260913_194900_4c03573a=telegram「aiチームに権限もっと与えれば…」,
  model=hy3, 23:08:18→23:27:24):
  - 最初の user 指示: "Review current Kensho anti-freeze measures and
    propose/implement improvements ... (1) bot detection evasion (human-like
    delays, action variance) (2) proxy/connection stability monitoring and
    auto-failover (3) session/token refresh robustness"
  - 23:19–23:24 に execute_code/write_file で applier.py(proxyなし)・
    proxy_watchdog.py(PROXY_POOL/auto_rotate)・session_manager.py
    (proactive_session_refresh) を編集。最終メッセージ: "All changes are
    complete and tests pass."
  - このセッションは git commit をしていない（DB内に git commit 呼出なし）→
    作業ツリーに未コミットのまま放置されたのが今回の dirty=Y の正体。
* 04:50:32 同一 mtime の証明:
  - pre-commit キャッシュ /home/atushi/.hermes/profiles/kensho-sweeps/home/
    .cache/pre-commit/patch1789415421-1701125 の mtime = 2026-09-15 04:50:21
  - これは run455(9/13) 以降の「pre-commit が変更を stash→restore して
    file mtime を一斉更新」した痕跡。再適用コマンドの実行履歴はどの
    profile の 04:4x–04:5x セッションにも存在しない。
* 全プロファイル state.db クロール結果: auto_rotate_proxy / proactive_session /
  consecutive_likes / gaussian を「書き込み」したのは 9/13 23:xx の
  当該サブエージェントのみ。9/15 04:4x–04:5x にこれらを書き込んだセッションは
  存在しない（revenue-worker 04:45 run457 は no-op、kensho-worker t_a8ede591 は別系統）。

================================================================
2. 変更5ファイルの分類・危険度
================================================================
[危険度: 高] kensho/utils/proxy_watchdog.py (+366)
  - 追加: PROXY_POOL / ACCOUNT_CLUSTER_MAP / ROTATION_CONFIG /
    auto_rotate_proxy() / auto_rotate_all_proxies() / get_proxy_health_report()
  - 問題: 「アカウント別SOCKS5 IP分離は絶対条件・変更禁止(2026-08-01確定)」と
    設計上正面衝突。垢別出口IPを自動で別クラスタへ切替える内容。
  - 現状: auto_rotate_* の呼出箇所は repo 内に一切なし（orchestrator は
    check_proxy_health のみ import）→ dormant。だが「分離ポリシー違反を
    自動化する関数」が生きているのは将来の誤呼出リスク。
  - 判定: HEAD へ還元（削除）。必要なら別途ユーザー承認を得て
    「分離維持のままヘルス監視のみ」に再設計。

[危険度: 中] config.yaml (+19/-19 見かけだが重複キー欠陥あり)
  - 欠陥1(重複schedule): kudou 配下に `schedule:` が2つ。YAML は後勝ちで
    kudou 本来のバッチ(08:24/10:03/.../22:28, 10件)が chugakujuken 旧バッチ
    (08:03/09:48/.../22:24, 10件) に静的上書きされている。
    → yaml.safe_load で確認: kudou.n_batches=10 だが時刻は 08:03..22:24（本来ではない）。
  - 欠陥2(wifi_profile消失): kudou の `wifi_profile: "a"` と zin20120731 の
    `wifi_profile: "AiR-WiFi_6_povo"` が削除済み。keepalive wifi_monitor の
    再接続プロファイル指定が落ちる懸念。
  - また chugakujuken アカウントブロック・USB-B インターフェース・関連 SSID
    参照の除去は「意図した cleanup」だが、上記のように kudou に重複ブロックを
    生じさせる形で行われた（sloppy edit）。
  - 判定: `git restore config.yaml` は HEAD(=chugakujuken復活)に戻るためNG。
    作業ツリー編集で「重複schedule削除 + wifi_profile復元 + chugakujuken清潔除去」が必要。

[危険度: 低・維持] kensho/application/applier.py (+202)
  - 人間らしさ強化: 読書時間の gaussian 化(85%通常/15%深読み)、アクション
    シーケンス記憶(直前2件同一で delay 1.5–2.5x)、夜型/バーストスタイル対応、
    スクロール回数・距離の削減。
  - 注: スクロール delay を (0.3,1.0)→(0.1,0.8) 等に「短縮」しており、
    一部はやや機械的になる方向。BOT回避には「ばらつき」が効いているため
    許容だが、delay 定数は要ユーザー目視確認（低リスク）。
  - いいね失敗時 consecutive_likes リセット: 過いいね検出を「弱体化」させる
    懸念あったが、コード確認では成功時のみ+1・失敗時0リセットで既存ロジック維持。
    問題なし。

[危険度: 低・維持] kensho/application/session_manager.py (+362)
  - v3.5 proactive session refresh/backup (proactive_session_refresh /
    get_session_health_report / recover_session)。repo 内呼出なし(dormant)
    だが既存関数を壊しておらず無害。将来のセッション枯渇予防として有用。維持。

[危険度: 低・維持] scripts/gen_status_data.py (-4)
  - chugakujuken 参照の除去（accounts リスト・WIFI_ADAPTER_TO_ACCOUNT・
    WIFI_ACCOUNT_SSID）。凍結垢の dashboard 統計除外として整合。維持。

================================================================
3. 監視拡張（v84教訓の適用）
================================================================
「dirty=Y は監視でなくトリアージ対象」を loop_health monitor に反映。
現状: board_state_monitor*.sh は `git status --porcelain -uall` で
コード変更1件以上→ dirty=Y（真偽値のみ）。同一秒 mtime の複数コード変更
= スクリプト一括適用の signature として検出・フラグ出力するよう拡張すべき。
→ 別タスク(scripts保守)で対応。本トリアージの監視側対応は「次runで dirty=Y が
継続する限り agent を起動させる（署名に dirty を含める既存挙動で達成済）」
で足りているが、bulk-apply フラグの追加を kensho-sweeps へ要望。

================================================================
4. 推奨ディスポジション（次runで実施）
================================================================
A. git restore -- kensho/utils/proxy_watchdog.py   (IP分離違反モジュール還元)
B. config.yaml 作業ツリー編集:
   - kudou 配下の重複 schedule ブロック(08:03..22:24側)を削除、本来(08:24..22:28)維持
   - kudou に wifi_profile: "a" / zin20120731 に wifi_profile: "AiR-WiFi_6_povo" 復元
   - chugakujuken アカウント+USB-B interface+関連SSID参照を重複キーなしで明示削除
C. applier.py / session_manager.py / gen_status_data.py は維持(py_compile+yaml確認)
D. 検証: yaml parse OK / py_compile OK / `git status --porcelain | grep -Ev
   'data/|reports/|html' | wc -l` → 0 / pytest 568pass 維持
E. commit + push origin main（メッセージに t_fa161ec9 束縛）

================================================================
5. 成功基準の状態
================================================================
次回 run までに dirty=Y が解決（コミット or リストア）されること。
本タスクは分析・トリアージ・提案が役割のため、実際の還元/修正は
kensho-sweeps へ子タスク委譲（kensho-worker の次run dirty チェックと連動）。
