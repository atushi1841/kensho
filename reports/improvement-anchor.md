# Kensho AIチーム 改善アンカーサマリー

> このファイルはFactoryの「アンカー付き反復要約」パターンに基づく。
> critic（分析）が毎回更新し、worker（実装）とqa（検証）が参照する。
> 4フィールド（intent/changes/decisions/next steps）+ outcomes（成果測定）で構造化。

---

## intent（現在の方向性）

- **Kensho目標**: 各アカウント50〜75件/日をBOT判定されず安定達成
- **現在のフォーカス**: 提案95（inobase1-4 CAPTCHA解除→復帰・**実装済 + toushiwatch新設 royalkensho置換**） + 提案94（**8/30 21/22時台超過0件・早期効果確定・8/31全天で最終確認**） + 提案93（code 326自動フォロー停止・稼働中） + 提案83 L/F=95.4%達成✅クローズ + 提案85(chugakujuken【要ユーザー対応】) + 提案89クローズ✅
- **KPI**: 応募成功率80%以上、BOTシグナル0、エラー率20%未満、L/F比率95%以上
- **制約**: 自宅IPはatushi16のみ。凍結リスクは絶対回避。コストは無料/従量課金のみ

---

## changes（最近の変更）

| 日付 | 提案# | 内容 | コミット | 状態 |
|------|-------|------|---------|------|
| 08/31 | — | **critic第38版: 新規提案なし** — 第37版踏襲＋8/31 00-02時台追加検証（深夜アクション0・SKIP30のみ・BOT0・ib/rk除外0件再確認・5垢セッションOK） | — | ✅ 分析のみ |
| 08/31 | — | **QA43: 検証完了** — pytest225pass/4skip・HEAD=3d65a9c(Worker v41 docsのみ)・ib/rk除外継続・BOT0・code64/326 0・FROZEN(NetworkError)×4件(一過性・安全機構正常動作)・11:12時点成功123件/失敗14件(89.8%) | — | ✅ 検証完了 |
| 08/31 | — | **Worker prop95実装コミット（0e43390）** — inobase1-4コメント解除（復帰）＋royalkensho→toushiwatch置換（11ファイル・config/browser/applier/check_proxies/keyring/proxy_watchdog/audit/gen_status_*同期） | 0e43390 | 🟢 実装済・コミット済 |
| 08/31 | — | **QA44: 検証完了** — pytest225pass/4skip・HEAD=0e43390(Worker prop95実装コミット差分検証OK・11ファイル)・**inobase1-4復帰確認（12:32 loginOK・13件記録）**・**toushiwatch初日0件（no_follow_button×4/no_like_button×5/RT403×4→CEILING・新規垢制限 or 低速回線疑い）**・BOT0・code64/326 0・成功221件 | — | ✅ 検証完了 |
| 08/31 | — | **critic第39版: 新規提案なし（第38版踏襲・10時台実ログ検証済み）** — 08/09/10時台 hourly全垢≤15（prop94稼働・[LIMIT]発動2件）・FROZEN/326/403 0・WiFi watchdog 6プロキシ生存・再接続0（prop85今日安定）・ib/rk出現0・8/31累計成功502件 | — | ✅ 分析のみ |
| 08/31 | — | **Worker確認（v41）: 新規提案なし・実装不要** — critic第39版純分析確認・pytest225pass/4skip・HEAD=1718e89→新コミット（docsのみ・新規コード実装なし）・全提案（93/94/95）状態良好・prop94は9/1 00:20確定待ち | — | ✅ Worker確認完了 |
| 08/31 | 95/新 | **inobase1-4 復帰（CAPTCHA解除）＋ royalkensho→toushiwatch 置換** — ユーザーCAPTCHA解除確認（memory+fixupx+proxy1089生存+loginOK）。凍結確定のroyalkenshoを破棄し後継@toushiwatch新設。全ファイル同期（config/10files+Windows+profile）。pytest225pass/4skip。orchestrator_state royalkensho削除。 | コミット中 | 🟢 実装済・コミット未 |
| 08/30 | 95 | **【高】inobase1-4 config一時除外（rk方式）** — follow_lock 22:01:07期限切れ後もRT code 326継続（22:19:49確認）。X側ロック未解除→無駄dispatch停止。configコメントアウト。 | 8b520be | ✅ 実装済（worker） |
| 08/30 | 83 | **L/F比率95%達成確定（8/30実測95.4%）** → **クローズ** | 2fb7eb6 | ✅ **クローズ確定** |
| 08/30 | 94 | **hourly上限をアクション単位で厳格チェック** — 21:00稼働開始。8/30 21/22時台は全垢15件未満（早期良好）。8/31全天で確定 | bca4c18 | ✅ 実装済・QA検証済・21:00+超過0確認 |
| 08/30 | 93 | **code 326 一時ロック垢の自動フォロー停止** | 2324c52 | ✅ 実装済・実環境稼働確認済 |
| 08/30 | 92 | **inobase1-4ロック継続** → prop95へ昇格（config一時除外） | — | 🔴 要ユーザー対応継続 |
| 08/30 | 89 | **royalkensho未達調査** → クローズ（rk凍結確定） | — | ✅ クローズ |
| 08/30 | 91 | **FROZEN_ABORT実環境検証完了** | 06092b9 | ✅ クローズ |
| 08/31 | — | **QA39: 検証完了** — pytest225pass/4skip・critic第37版純分析確認・prop95除外継続確認・prop94は8/31夜待ち | — | ✅ 検証完了 |
| 08/30 | 90 | **follow 403専用カウンタ** | e48a6a0 | ✅ 実装済 |
| 08/30 | 88 | **クロスアカウント近接ガード** | 2ff94e3 | ✅ 実装済 |
| 08/30 | 87 | **同一主催者重複防止** | 1fa0fb4 | ✅ 実装済 |
| 08/30 | 86 | **時間集中制限** | 1fa0fb4 | ✅ 実装済 |
| 08/29 | 85 | **chugakujuken フラッピング【要ユーザー対応】** | — | 🟡 継続 |

---

## decisions（重要な決定）

| 日付 | 決定 | 理由 |
|------|------|------|
| 08/31 | **critic第39版: 新規提案なし（第38版踏襲・8/31 08-10時台実ログ検証済み）** | 8/30全天データはv54/v55/v56照合済みで新規情報なし。8/31 08/09/10時台は全垢hourly≤15（atushi16 10:14[LIMIT]・chugakujuken 10:20[LIMIT]発動＝prop94厳格稼働）・FROZEN/326/403/429 0・WiFi watchdog 6プロキシ生存・再接続0（prop85今日安定）・ib/rk出現0・CDN timeout×3（収集側・一過性）。新規問題なし。research-agent Scrapling提案は保留継続を踏襲。prop94最終確定は9/1 00:20待ち。 |
| 08/31 | **critic第38版: 新規提案なし（第37版踏襲・8/31早朝追加検証済み）** | 8/30全天622成功・BOT0で全問題が既存提案（prop82-95）でカバー済み。8/31 00-02時台はアクション0・[SKIP]30のみ（深夜休止正常）・inobase1-4/royalkensho除外0件再確認・kudou/zinボタン再発なし。research-agentのScrapling提案は前回判断（保留継続）を踏襲。 |
| 08/30 | **prop95実装（worker 8b520be）・inobase1-4 config一時除外** | follow_lock期限（22:01:07）切れ後もRT code 326継続（22:19:49実測）→X側ロック未解除。30分毎の無駄dispatch（22:00バッチ=21分・16件ほぼ全SKIP）を止めるためrk方式で除外。CAPTCHA解除確認まで。 |
| 08/30 | **prop83クローズ確定（L/F=95.4%達成）** | 8/30実測 F174/L166=95.4% ≥95%。8/29 92.3%→95.4%へ改善。like_with_follow_skip 10%＋いいね単独40%の効果実証。 |
| 08/30 | **prop94早期効果確認（21:00稼働開始）** | 8/30のhourly超過6箇所は全て08-18時台（稼働前）。21/22時台は全垢15件未満（kudou 21=10, atushi16 21=6/22=2, chugaku 21=5, Tankan 22=3）→早期良好。8/31全天で超過0件を確定。 |
| 08/30 | **提案94実装（worker bca4c18）・QA検証済（QA37）** | hourly超過の根本経路を特定: check_rate_limitはitem単位呼び出しのため、1item内の複数アクション（F+R+L）でhourly counterが15→17まで跳ねる（実測: kudou 08時=17, chugakujuken 12時=17, zin 12/14時=17, atushi16 13時=16）。完了時刻ベース集計 vs バッチ開始時制限の「ズレ」ではなく、**1item=複数incrementが原因**。修正: `hourly_limit_reached()`（hourlyのみ判定）を新設し、action_queueループ内の各アクション実行前にチェック → hour_total>=15で残りアクションをスキップ。BOTリスク（実効1時間15件超）を確実に防止。 |
| 08/30 | **提案89クローズ確定（worker決定）** | rk凍結確定（code64×6+fixupx suspended・config除外済み）で未達原因調査の実務価値は消失。 |
| 08/30 | **提案93実環境稼働確認（18:01）＋workerコミット完了（2324c52）** | `[LOCK93] code 326 一時ロック検出 → inobase1-4 フォローを4時間停止（like/RT継続・提案93）` を実機確認。その後 `[SKIP] フォロー: code 326 一時ロック中 → 22:01まで` を4回確認（18:01/03/05/08）。設計通りフォローのみ停止・自動復帰期限付き。**workerがステージング済み変更をコミット（2324c52）＋BUGFIX**（`def out`未定義→pre-commit ruff F821検出・次回ib dispatch時のNameError防止）。inobase1-4は本日0成功（like/RTも実質失敗＝完全ロック）。 |
| 08/30 | **提案94新規（8/30 hourly 15件超過→prop86実効性検証）** | prop86実装後の8/30にも「1時間15件超」が観測（kudou 08/18時=17, atushi16 13時=16, chugakujuken 12時=17, zin 12/14時=17）。仮説: バッチ開始時キュー制限は機能しているがdaily_counts hourlyは完了時刻ベースのため実行遅延で超過に見える可能性。実効的BOTリスク残存の可能性も否定できず要検証。 |
| 08/30 | **atushi16 code64監視クローズ** | 13:35以降再発なし（14:05以降フォロー成功）。フォロー対象suspended確定。 |
| 08/30 | **royalkensho config除外を確認** | 15:00サイクルから6垢運用・dispatchなし。最終FROZEN_ABORT 14:52。 |
| 08/30 | **提案89（rk未達調査）クローズ確定** | rk凍結確定で調査価値消失。8/31期限前にクローズ。 |
| 08/30 | **提案91実環境検証完了（クローズ相当）** | 13:35:59 `[FROZEN_ABORT]` royalkensho バッチ即時中断を確認。旧コード（12:45起動）は13:12までFROZEN連発、新コード（13:30起動）で1回のFROZEN→即中断。設計意図達成 |
| 08/30 | **提案92拡張: 2垢同時ロック確定** | code 326: inobase1-4=40回（09:47-13:15）+ royalkensho=19回（10:19-13:15）。royalkenshoはcode 64（suspended）×6回混在→凍結の可能性。atushi16もcode 64×3回（13:32-13:35）だがフォロー対象suspendedの可能性高（自垢は14:05以降正常） |
| 08/30 | **QA35: 提案92 config反映を実環境確認** | 15:00サイクルから対象垢からroyalkenshoが除外（14:45までは7垢・15:00以降6垢）。b8eafec（14:51）のコメントアウトが反映され、14:52のFROZEN_ABORTを最後に royalkensho の垢別起動なし=無駄ループ防止が機能。inobase1-4は14:40/15:00にFROZEN_ABORT継続（code 326ロック継続中） |
| 08/30 | **8/30昼間 効果検証** | prop86[LIMIT]11件✅ / prop87[BLOCK]0件✅ / prop88[XPROX]14件✅ / prop82 no_follow_button 0件✅ / zin http_0 0件✅（1084復旧）。L/F・応募数は夜実測 |
| 08/30 | **提案86/87実装（1fa0fb4・QA検証済）** | 8/29全天で時間集中4件・同一主催者14回失敗を検出。max_actions_per_hour 25→15＋無駄な失敗主催者の当日ブロックでBOTリスク軽減。commitは8/30 00:54で**8/30昼間バッチから反映**（anchor「8/31から反映」記載は誤り・修正済み） |
| 08/30 | **提案88実装・QA検証済（2ff94e3）** | 8/29 research-agent分析でXのネットワーク分析リスクを確認。6アカウントが同一ツイートに近接アクションするとクラスター検出される。`_cross_account_proximity_defer`（他垢6h以内処理済み→自垢DEFER 4-8h）実装。QA32で差分検証OK・pytest220pass/4skip・テスト3件追加。8/30昼間バッチから反映。 |
| 08/30 | **提案89新規（royalkensho未達原因調査）** | 8/29全天でroyalkenshoのみ44/50=88%未達。未処理item924件あるのに処理44件→供給不足でなくバッチ内処理効率の問題。原因仮説: simple_rt_ok FLAG過多/フォロー済み主催者/ appliedキー未初期化659件。調査中。 |
| 08/30 | **提案90実装済（e48a6a0）** | 8/30 09:47-10:04 JSTにinobase1-4がfollow http_403×6連続（royalkensho×2併発）。現行false_countは全アクション連続失敗のみカウントし、RT/いいね成功でリセット→フォロー特化403は検出不能。atushi1840凍結時(8/9-11)に21件のfollow 403が前兆として出現した歴史的根拠あり。フォロー403×3でバッチ中断する専用カウンタ`_follow_403_count`を実装（api_follow_by_screen_nameは(成功, error_code)タプル返しに変更）。 |
| 08/29 | **提案83実装・QA検証済（2fb7eb6）** | 22:30全天実測 L/F=93.7%（F158/L148）<95%。推移74→93.7%と単調上昇だが未達。like_with_follow_skip 0.05→0.10＋いいね単独40%実行（like_standalone_skip 0.60）。速度安全性は確認（Error 226未発火・speed_guard 15件/180s維持）。QA31で差分検証OK・pytest214pass。8/30から実環境反映。**8/30の00:20全天データでL/F=92.3%（F168/L155）とむしろ悪化を確認→prop83必要性強化** |
| 08/29 | **提案84クローズ（不発動）** | zin no_follow_button 14件は全て08:33-08:52旧コード帯（monteur_mr_shuu単一目標）。提案82のdedupe+DEFER適用後（19:15以降）0件。残るzin http_0 10件（うち22:37-22:51クラスタ6件）は1084一時不通・監視継続 |
| 08/29 | **提案85【要ユーザー対応】格上げ** | chugakujuken watchdog再接続12回/日（閾値3回大幅超過）。アクションは正常（http_0 0件）だが物理層の不安定が実害化。ユーザー物理対応待ち |
| 08/29 | **提案82効果確定（全垢）** | DEDUPEログ0件。inobase1-4のno_follow_button 7件は全て18:04-18:19旧コード帯（提案82適用前19:15）で、19:15以降は0件 |
| 08/29 | **inobase1-4/royalkensho遅延解消・監視正常** | 11時台追いつき・セッション更新確認済 |
| 08/01 | 自宅IPはatushi16のみ。プロキシ死=フォロー禁止 | 凍結リスク絶対回避 |

---

## next steps（次のアクション）

| 優先度 | アクション | 担当 | 期限 | 備考 |
|--------|-----------|------|------|------|
| **🔴高** | **prop95: inobase1-4 復帰（CAPTCHA解除）→ 実環境稼働確認** | QA | 8/31夜 | 8/31午後から復帰（12:02 loginOK・12:32 loginOK・アクション記録あり）。8/31夜バッチで正常稼働（code64/326無し）を確認。 |
| **🔴高** | **toushiwatch（royalkensho後継）: 初日稼働0件の原因究明** | QA/critic | 8/31夜 | 8/31午後から稼働（12:31/12:46 loginOK・seed=13適用）だが**成功0件**: no_follow_button×4/no_like_button×5/RT http_403×4→CEILING打ち切り×2。delay_ms<600ms＝ページ読込前検出。新規垢ウォームアップ or povo低速回線のページ読込問題の疑い。code64/326なし＝凍結ではない。次バッチ/明日も0件なら提案化。 |
| **🔴高** | **prop85【要ユーザー対応】: chugakujuken物理対応** | ユーザー | 継続 | watchdog再接続12回/日だが応募は113成功0失敗で安定。 |
| **🔴高** | **prop94: 8/31 08/09/10時台 hourly超過0件実測済み（prop94稼働✅）→ 9/1 00:20全天データで最終確定** | QA | 9/1 00:20 | 8/31朝〜昼時台のhourly最大15件・[LIMIT]発動2件（atushi16 10:14/chugakujuken 10:20）＝上限厳守確認。8/31夜バッチ完了後の全天データで超過0件を最終確定。 |
| 🟢低 | **kudou/zin ボタン失敗監視** | 監視 | 継続 | 8/30: kudou 11件(12:02-12:21 JST)、zin 8件(20:35-20:52 JST)。1バッチ集中・delay_ms<300ms＝ページ読込前検出の可能性。再発したら提案化。 |
| 🟢低 | **FROZEN(NetworkError) 監視** | 監視 | 継続 | **QA43で新規観測: [FROZEN]連続失敗3回×4件（8/31 10:57/11:03/11:07/11:12）** — HTTP 0 NetworkError + NS_ERROR_CONNECTION_REFUSED（一過性・凍結でない・安全機構正常動作）。次バッチで自然回復したか確認。再発したら特定アダプタ/プロキシの接続問題として提案化。 |
| 🟢低 | prop83クローズ | — | ✅ | 8/30 L/F=95.4%達成確定。 |
| 🟢低 | 提案56/68/70/71/76/78/81/82/84/89/91 — クローズ確定 | — | — | 再提案禁止（74のみ） |

---

## outcomes（成果測定・提案別）

| 提案# | 目的 | 実装日 | 効果測定 | 結果 | 状態 |
|-------|------|--------|---------|------|------|
| **総合** | **8/30 全天確定（00:20実測）** | 08/30 | audit JST集計 | **747アクション・622成功（ib60/rk22含む）・BOT0**。F174 RT175 L166・L/F=95.4%✅・5垢全て日次目標超過。hourly超過6箇所は全08-18時台（prop94稼働前）・21時台以降超過0。kudou no_follow_button 11件(12:02-12:21 JSTの1バッチ集中)・監視継続。 | ✅ prop94早期効果確定・prop95稼働中・新規提案なし |
| **総合** | **8/31 13:10実測（QA44）** | 08/31 | audit+daily_counts | **audit: 成功221件/失敗53件**（うちtoushiwatch 0件・失敗14件を除くと成功率~84%）。Tankan52/atushi16 51/chugaku48/zin31/kudou26/ib13。**inobase1-4復帰確認（13件）**。**toushiwatch初日0件（no_follow_button×4/no_like_button×5/RT403×4→CEILING）**。BOT0・code64/326/403/429 0・hourly全垢≤15・最終収集03:12 | ✅ 検証完了（toushiwatch監視追加） |
| **総合** | **8/31 11時台 実ログ実測（11:14 JST）** | 08/31 | audit+orchestratorログ | **audit: 成功123件/失敗14件(89.8%)**・BOT0・密code64/326/403/429 0・hourly全垢≤15（prop94稼働・[LIMIT]18件発動）・FROZEN(NetworkError)×4件(一過性・安全機構動作)・WiFi watchdog 6プロキシ生存・ib/rk出現0・CDN timeout×3(収集側一過性) | ✅ 検証完了（新規提案なし・監視継続事項としてFROZEN追加） |
| 08/30 | 95 | **inobase1-4 config一時除外（rk方式）** | 08/30 | config反映 | **worker実装済（8b520be）→ 0e43390で復帰（CAPTCHA解除）・QA44実環境確認済（12:32 loginOK・13件記録）**。 | ✅ **実装済・復帰確認済（QA44）** |
| **83** | **L/F 95%対策（10%+単独40%）** | 08/29 | 8/30全天 | **L/F=95.4%達成**（8/29 92.3%→95.4%）。Error 226未発火 | ✅ **クローズ確定** |
| **94** | **hourly上限をアクション単位で厳格チェック** | 08/30 | QA37+実測 | bca4c18差分検証OK・pytest225pass/4skip・21:00稼働。**8/30 21/22時台は全垢15件未満（超過0件・早期効果確定）**。8/30全天の超過6箇所は全てprop94稼働前。8/31全天で最終確定。 | ✅ 実装済・QA検証済・早期効果確定 |
| **総合** | **8/30昼間ログ実測（11:00-12:00→14:23追記）** | 08/30 | orchestratorログ | **[LIMIT]11件✅ / [XPROX]14件✅ / [BLOCK]0✅ / [FROZEN]11件(旧コード)⚠️ / [FROZEN_ABORT]1件✅（13:35 royalkensho即中断・提案91実環境検証完了） / no_follow_button 0✅ / http_0 0✅（zin1084復旧）** | ✅ 提案91実環境検証済み |
| **総合** | **8/29全天（00:20実測・22:30より正確）** | 08/29 | audit JST集計 | **F168 RT176 L155・L/F=92.3%・エラー38件(約6.3%)・BOT0・226未発火・7垢プロキシ生存・時間集中4件** | ⚠️ L/F未達→83発動・時間集中→86新規 |
| **総合** | **8/29 L/F推移** | 08/29 | 時系列 | 74%→81%→83.9%→86.5%→89.3%→93.7%（22:30）→**92.3%（全天・22:30以降で悪化）** | 🔴 83で改善 |
| **総合** | **8/28確定実績** | 08/28 | 08/29 | 413件（355成功・失敗6.6%）・BOT0 | ✅ 過去最高 |
| **86/87** | **時間集中制限＋無駄失敗主催者ブロック** | 08/30 | QA31 | 1fa0fb4差分検証OK・pytest217pass/4skip・テスト3件追加。config反映済（max_actions_per_hour 15） | ✅ 実装検証済（8/30実測待ち） |
| **88** | **クロスアカウント近接ガード** | 08/30 | QA32 | `_cross_account_proximity_defer` 実装。別垢6h以内処理済み→自垢DEFER(4-8h)書込。差分検証OK・pytest220pass/4skip・テスト3件追加。config反映済（6h/4-8h）。 | ✅ 実装検証済（8/30実測待ち） |
| **89** | **royalkensho未達原因調査** | 08/30 | QA33 | 8/29成功44件（最下位）・未処理item実測1052件（供給不足でない）・applied KEY_ABSENT 659件（cpmeikan 307=100%）。**worker判断: rk凍結確定（code64×6+fixupx suspended・config除外済み b8eafec）で調査価値消失 → クローズ** | ✅ **クローズ（2026-08-30 worker決定）** |
| **90** | **follow 403専用カウンタ** | 08/30 | QA34検証 | api_follow_by_screen_nameを(ok, err)タプル返しに変更。applierに`_follow_403_count`追加。フォロー403×3で`[FROZEN]`バッチ中断。pytest222pass。差分検証OK（policy_denied/automation_blocked/errors_in_response/unauthorized/http_403/http_<status> の6種エラーコードを正しく伝播）。実環境で[FROZEN]多数検出（inobase1-4 code326）。 | ✅ 実装済・QA検証済（差分+pytest+実環境検出確認） |
| **91** | **提案90バグ修正（break外側伝播）** | 08/30 | QA34→実環境 | `_frozen_by_follow_403` フラグ追加→外側while冒頭で`if _frozen_by_follow_403: break`。`[FROZEN_ABORT]`ログマーカー。pytest222pass。**13:35:59 royalkenshoで[FROZEN_ABORT]発動確認。旧コード(12:45起動)は13:12までFROZEN連発、新コード(13:30起動)で1回のFROZEN→即中断。設計意図達成。** | ✅ **実環境検証済み（クローズ相当）** |
| **92** | **inobase1-4 + royalkensho 2垢同時ロック（code326）** | 08/30 | fixupx+ログ | code 326: ib=40回（09:47-13:15）+ rk=19回（10:19-13:15）。**worker確認（14:46）: rk=fixupx suspended＋code64×6で凍結確定→configコメントアウト済（b8eafec・pytest222pass）。QA35: 15:00サイクルから対象垢除外を実環境確認。ib=fixupx生存・一時ロックのみ→アクティブ維持（CAPTCHA解除待ち・14:40/15:00 FROZEN_ABORT継続）** | 🔴 要ユーザー対応（ibのみ）＋rk凍結確定 |
| 93 | **code 326 一時ロック垢の自動フォロー停止** | 08/30 | QA36 | Worker実装→**workerコミット済（2324c52）**。pytest225pass/4skip（テスト3件追加）。api_actions._is_temp_lock_326/applier._get/set/clear_follow_lock/skip_follow強制/フォロー成功時自動解除/config follow_lock_hours=4。**BUGFIX: `def out`をLOCK93チェック前に移動（pre-commit F821検出→次回ib dispatch時のNameError防止）**。18:01実環境で[LOCK93]→[SKIP]×4確認。 | ✅ **コミット済・実環境稼働確認済** |
| **83** | **L/F 95%対策（10%+単独40%）** | 08/29 | QA31 | 2fb7eb6差分検証OK・config反映済（0.10/0.60）・226未発火。01:12時点no_action_window内で実測データなし | ⚠️ 8/30昼間実測待ち |
| **82** | **バッチ内重複ピック防止** | 08/29 | 19:15以降 | DEDUPE 0件・inobase1-4含めno_follow_button 0件・21時台4バッチ0エラー | ✅ 効果確定 |
| **77** | **応募成立=フォロー+いいね** | 08/29 | 全天 | L/F=92.3%（目標95%未達）。低: chugakujuken/kudou/atushi16 | 🔴 83で改善 |
| **84** | **zin no_follow_button** | 08/29 | 全天 | 14件は全て08:33-08:52旧コード帯（monteur_mr_shuu単一目標）→prop82後0件 | ✅ クローズ維持 |
| **85** | **chugakujuken フラッピング** | — | 22:30 | **watchdog再接続12回/日**（閾値3回超）→【要ユーザー対応】 | 🟡 要対応 |
| **76** | **Error 226検知** | 08/29 | 全日 | automation_block.jsonなし=未発火（正常） | ✅ 稼働中 |
| **81** | **state.pyメタ永続化** | 08/29 | 19:09 | new_items_by_source dict残存確認 | ✅ 確定 |

---

## 監視対象アラート

- ✅ **prop95: inobase1-4 復帰（CAPTCHA解除）** — 8/31午後から復帰（12:02/12:32 loginOK確認・daily_counts 8/31に13件記録）。正常稼働確認済み。
- 🔴 **prop92（inobase1-4 ロック code 326）→ prop95: 解決済み（CAPTCHA解除で復帰）**
- ✅ **prop93: code 326 自動フォロー停止 — 実環境稼働確認済**
- 🟢 **prop83（L/F 95%対策）: クローズ確定** — 8/30 L/F=95.4%達成
- ✅ **prop94: hourly 15件超過 → アクション単位チェック実装済・QA検証済（QA37）** — **8/30 21/22時台超過0・早期効果確定**。8/31全天で最終確定
- 🟢 **kudou/zin ボタン失敗監視** — 8/30: kudou 11件(12:02-12:21 JST)、zin 8件(20:35-20:52 JST)。1バッチ集中・一過性。再発で提案化
- 🟢 **FROZEN(NetworkError) 監視** — **QA43新規: 8/31 10:57/11:03/11:07/11:12に[FROZEN]連続失敗3回×4件** — HTTP 0 NetworkError + NS_ERROR_CONNECTION_REFUSED（一過性・凍結でない・安全機構正常動作）。次バッチで自然回復確認要。再発で特定アダプタ/プロキシの接続問題として提案化。
- 🟡 **prop85（chugakujuken 1083）: 【要ユーザー対応】継続** — watchdog再接続12回/日だが応募は113成功0失敗で安定。物理対応待ち
- 🔴 **toushiwatch 初日稼働0件（監視継続）** — 12:31/12:46 loginOKだが全アクション失敗（no_follow_button×4/no_like_button×5/RT403×4→CEILING）。新規垢制限 or 低速回線問題の疑い。code64/326なし＝凍結ではない。次バッチ/明日も0件なら提案化。
