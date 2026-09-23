# t_66c14eb4 検証レポート — 自律稼働工場化 後続観測: self_heal 実効の本番検証

- タスク: t_66c14eb4（QA検証・記録のみ。コード変更なし）
- 親タスク: t_fa046d3a（自律稼働工場化 実装、done 済み）
- 実測時刻: 2026-09-24 02:33〜03:00 JST
- 対象: `kensho/core/self_heal.py`（配線 commit f906e3a / 2026-09-22 13:22:42、production 初回発動 2026-09-22 12:52:20）
- 検証手法: 一次ログ（`logs/auto_*.log`, `logs/collect_*.log`）と `data/self_heal_state.json` の読み取り専用解析。コードは一切変更していない。

## 結論（受け入れ条件の判定）

| 受け入れ条件 | 判定 | 根拠 |
|---|---|---|
| self_heal の発動事例（リトライ/リカバリ）がログに1件以上ある | **PASS** | apply側 32件 + collection側 4件 = **計36件の自己修復最終失敗**を一次ログで確認。全件 `attempts=3` = ループが3回転した実測値。さらに22/32件で「3回目の操作再実行トレース」をログ上で完全一致復元 |
| before/after 数値KPI を evidence.json に記録 | **PASS** | `reports/t_66c14eb4_evidence.json` の `outcome` に6件の数値KPIを記録 |

タスク内容3の「48時間稼働後の実測」は**未達（観測窓不足）**: 導入からは37.7時間、最終失敗からは4.4時間（うち apply の露出は 0 回）。この点は追跡タスクで再測する（本レポート末尾）。

## 一次証跡の所在（ログ体系が2系統に分かれている点に注意）

self_heal の最終失敗は**ログ体系が2系統**に分かれて出る。apply 側は集約ログ、collection 側は収集専用ログのみで、**どちらの系統も self_heal 自身の回復イベントは1行も出していない**（後述 F6）。

- apply: `logs/auto_YYYYMMDD.log` の `[NG] applyエラー: self_heal failed: ... (attempts=3)`（1失敗あたり3行 = 例外行＋`raise` ソース行＋`RuntimeError:` 行）
- collection: `logs/collect_YYYYMMDD_HHMMSS.log` の `RuntimeError: self_heal failed: ... (attempts=3)`（呼出側で捕捉されずプロセスが異常終了）
- 状態: `data/self_heal_state.json`（`ceilings.apply` / `ceilings.collection`）

### apply 側の生ログ（抜粋・原文）

    2026-09-22 15:06:28.240 | INFO | kensho.core.logger:write:48 -   [NG] applyエラー: self_heal failed: apply 0 success 1 errors (attempts=3)
      File "/mnt/d/Project2/kensho/kensho/core/self_heal.py", line 79, in value_or_raise
    RuntimeError: self_heal failed: apply 0 success 1 errors (attempts=3)

### collection 側の生ログ（失敗した4 run はすべてこの形でプロセス異常終了）

    2026-09-23 20:00台 logs/collect_20260923_200001.log:
    RuntimeError: self_heal failed: _collect_impl.<locals>.<lambda>() missing 3 required positional arguments: 'out', 'ps', and 'ak' (attempts=3)

## apply パイプライン実測

- 自己修復最終失敗: **32件**（全件 `attempts=3`、メッセージは全件 `apply 0 success 1 errors`）
- 初回 2026-09-22 15:06:28 / 最終 2026-09-23 22:19:25
- 日別: 09-22 = 7件、09-23 = 25件
- 障害アカウント帰属: **zin20120731 = 29件（90.6%）**、TankanNotes = 2件、atushi16 = 1件
  - 直前の操作開始行から遡る帰属推定。zin20120731 は `[OK] Session: @zin20120731 OK（最終更新: 5日前）` が 2026-09-23〜09-24 02:33 まで**一貫して5日前のまま**＝セッション（auth_token）失効が2日間放置されていた
- 導入直後の配線バグ: `SelfHealingLoop.__init__() got an unexpected keyword argument 'logger'` が **2件**（2026-09-22 12:52:20 / 12:53:52）。f906e3a が 13:22:42 コミットのため、それ以前は applier 側だけ新しく self_heal 側が旧版という部分配備状態だった（現在は解消）

### リトライが実際にログへ残っていることの突き合わせ（本タスクの中核検証）

`attempts=3` はコードが返す値なので、ログ上の実トレースと突き合わせた。self_heal の retry は操作（`_apply_impl`）を再実行するため、`[Kensho] アカウント: @<key> (<key>)`（applier.py:919）が再出力される。この行を「同一アカウント・間隔900秒以内」で連鎖させて復元した:

- 復元した試行数が `attempts=3` と**完全一致 = 22件**（例: 15:06:28 失敗 ← 14:53:56 / 14:57:02 / 15:03:20 の3件）
- 試行トレースが3件以上復元できたもの = **27件 / 32件**
- 残りは同時並列ディスパッチ（最大7垢同時）との混線およびグレース内の早期 return により復元数が合わないもので、retry 不発を意味しない

→ **「エラー→自動リトライ」は推測ではなく一次ログで実証された。**

## collection パイプライン実測

- 自己修復最終失敗: **4件**（全件 `attempts=3`）、すべて 2026-09-23 の 17:00 / 18:00 / 19:00 / 20:00 の毎時収集
- メッセージ内訳: `guarded_source() got an unexpected keyword argument 'proxy'` ×1、`<lambda>() missing 3 required positional arguments: 'out','ps','ak'` ×3 = 同一の引数不整合バグ
- 帰結: 自己修復が3回転した末に `value_or_raise()` が送出され、**収集runが丸ごと異常終了（収集データ0件）**
- 根治: commit 290c480（2026-09-23 21:27:04、`guarded_source` 引数不整合の修正 + 回帰テスト168行）
- 修正後の収集run: `logs/collect_20260923_210002.log` = 自己修復失敗 0件・完了（36989 bytes）。`Traceback` 0件

## before/after KPI（実測値）

| KPI | before | after |
|---|---|---|
| apply 自己修復最終失敗レート（件/時間） | 0.952（09-22 12:52:20〜09-23 21:27:04、32.58h で 31件） | 0.186（09-23 21:27:04〜09-24 02:50、5.38h で 1件） |
| apply 操作開始あたり最終失敗率 | 20.81%（31/149操作開始） | 33.33%（1/3操作開始）※分母3で統計的意味なし |
| collection 自己修復最終失敗率（収集runあたり） | 100%（09-23 17:00〜21:27 の 4run 中 4run 失敗＝収集全停止） | 0%（09-23 21:27〜09-24 02:50 の 1run 中 0run 失敗・完了） |
| self_heal の最終失敗の可観測件数（ログから復元） | 導入前 0件 | 36件（apply 32 + collection 4） |
| 1失敗あたりの試行回数（実測） | — | 3.0（36/36件が `attempts=3`） |
| 最終失敗以降の apply 露出（操作開始数） | — | **0回**（＝「失敗ゼロ」は露出ゼロによる右打ち切り） |

自己修復最終失敗の**直前**窓（最終失敗 2026-09-23 22:19:25 以降）は apply の操作開始が0回のため、**「失敗ゼロ」を改善の証拠として使えない**。この区間の apply 操作開始が0回である理由は `logs/auto_20260924.log` の全ディスパッチが `処理待ちのバッチなし` を返しているため（深夜帯で対象バッチ0）。

## BOTシグナルへの影響（最重要・強調）

self_heal の retry は**操作（＝ブラウザ起動とXログイン）を丸ごと再実行する**。セッション失効アカウントに対して盲目的に3回転した結果、ログイン試行が増幅した:

| 日 | `[NG] goto failed (attempt N)` | `[NG] ログイン失敗 - auth_tokenが必要` | `Xにログイン確認中` |
|---|---|---|---|
| 09-18 | 18 | 6 | 55 |
| 09-19 | 43 | 14 | 43 |
| 09-20 | 63 | 21 | 54 |
| 09-21 | 36 | 12 | 40 |
| 09-22 | 81 | 27 | 67 |
| 09-23 | **227** | **75** | **108** |

- `goto failed` は 09-20 の 63 から 09-23 に **227（3.6倍）**、`auth_tokenが必要` は 09-21 の 12 から **75（6.25倍）**
- `Xにログイン確認中`（＝実ログイン試行回数）は 09-18〜09-21 の基準値 約40〜55回/日 に対し 09-23 は **108回/日（約2.2倍）**
- 09-23 の apply 失敗 25件はいずれも `attempts=3` なので、同一セッション失効アカウントに対して **約50回の追加ログイン試行**が self_heal の retry により発生した計算になる（108 − 基準約55 ≈ 53 と整合）
- 失敗の直前は必ず `[NG] ログイン失敗 - auth_tokenが必要` → `DEBUG: browser closed` → `[MEM] gc.collect` の順で、X側から見ると「ログイン失敗→即ブラウザ終了」を短時間に反復するパターンになっている

**判定: self_heal は BOTシグナルを低減するどころか、失効セッションのアカウントに対してログイン失敗リトライを約2倍に増幅した。** 原因は後述 F3（回復アクションに session/auth 系が無い）にあり、retry を増やす方向の調整（max_attempts 増加）は**行ってはならない**。

## 検出した設計上の欠陥（実測に基づく）

- **F1 self_heal の回復イベントが一切ログに残らない（可観測性ゼロ）**
  `SelfHealingLoop.__init__` は `logger` を受け取るが、`self.logger` は代入のみで**どこからも使われていない**（`grep -n logger kensho/core/self_heal.py` は 312 と 318 の2行のみ）。`HealingEvent`（どの回復アクションが何をしたか）はメモリ上で捨てられ、`value_or_raise()` の最終失敗だけが呼出側のログに出る。今回 retry の実在を証明するために操作開始行の時系列復元を要したのは、この欠落の直接の帰結。

- **F2 `ai_assisted: false` がコードから読まれていない（設定が不活性）**
  `grep -rn ai_assisted` の当たりは config.yaml のコメント/設定行、self_heal.py の既定値、テストのみで、**self_heal.py の実行経路に参照が無い**。既定の回復順 `jitter_retry → network_check → ai_consult → transport_fallback → scope_reduction` のまま attempt index 1 で `ai_consult` が必ず選ばれる。しかも本番に `OPENROUTER_API_KEY` が無い（プロジェクト `.env` に OPENROUTER 系キーなし）ため `_ai_consult` は `("none", "no_openrouter_api_key")` を返すだけの**確実な no-op** になる。

- **F3 回復順に session/auth 系アクションが無く、分類も届かない**
  `_builtin_action` に `session_retry` は実装されているが既定の `order` に含まれない。加えて validator 由来のシグナルは `classify_error` を通らず `signal.kind = "apply_zero_success"` になるため、`_SESSION_MARKERS`（session/auth/cookie/login/401/403）による分類が働かない。結果、auth 失効は「apply 0 success 1 errors」としか見えず、`network_check` が `network_ok` を返して**何も変えずに再試行**するだけになる。

- **F4 `max_attempts=3` では回復順の後半2アクションに到達しない**
  `_choose` は attempt 0 で必ず `jitter_retry`、attempt 1 で必ず `ai_consult`、attempt 2 で `order` の最初の非jitter/non-ai 要素（=`network_check`）を返す。試行は3回で尽きるため `transport_fallback` と `scope_reduction` は**構造的に一度も実行されない**。

- **F5 failure ceiling が実質的に機能しない（毎時cronでは絶対に発動しない）**
  `_record_ceiling(hit=True)` は `first_fail_time` を `setdefault` で**初回のみ設定し以降更新しない**（self_heal.py:342-344）。`_is_ceiling_hit` は「count>=3 かつ now − first_fail_time < 30分」で判定するため、初回失敗から30分を過ぎると永久に False になる。毎時実行の collection では**隣接runが60分間隔なので遮断が起こり得ない**。実測: collection は 17:05 / 18:03 / 19:03 / 20:13 と4連続で失敗したが、一度も `failure_ceiling_blocked` にならなかった。
  さらに ceiling のキーは `ctx.get("key") or self.pipeline` = `"apply"` 固定で**アカウント粒度がない**。全アカウント共通カウンタなので、特定垢の失敗は他垢の成功（`_record_ceiling(False)`）で毎回 0 に戻される。実測: 失効垢 zin20120731 の失敗が29件集中しても ceiling は発動せず、`data/self_heal_state.json` は `apply.count=0` / `collection.count=0` のまま（`first_fail_time` だけが apply=2026-09-22T15:06:28.137352、collection=2026-09-23T17:01:53.345701 と残存＝「1回はヒットしたが成功でリセットされた」ことの証明）。

- **F6 config.yaml の自己修復フラグが呼出側のハードコードで上書きされる**
  collector.py:259 は `context={"retry_empty_collection": True}` とハードコードするため config の `retry_empty_collection: false` は無効。applier.py:712 も `context={"retry_partial": False}` 固定で `retry_partial_apply: true` にしても効かない。設定と実挙動が乖離している。

## config.yaml `self_healing` 調整案（タスク内容4）

コード変更を伴わない（＝QAの権限内で出せる）案を優先度順に示す。**F1/F4/F5の恒久修正はコード変更なので、本タスクでは提案に留め、実装は別タスクとする。**

1. **`ai_assisted: false` を実効化する（コード or 設定）**
   - 設定のみの回避策: 既定 `order` の `ai_consult` を無効化できないため、現状の設定だけでは no-op 試行を消せない → コード側で「`ai_assisted` が false なら `ai_consult` を order から除外」する1行変更を別タスクで実施するのが本筋。
   - 暫定の設定回避策: `ai_model: ""` のままとし、`.env` に OPENROUTER キーを**追加しない**（現状維持）。追加すると本番の失敗時に外部LLM呼び出しが発生し、しかもその推奨は実行されない入力（`context={}` / `error_info=""` で呼んでいる: self_heal.py:495）なので費用だけ発生する。

2. **failure ceiling を毎時cronで実際に効かせる**
   - 設定のみの候補: `failure_ceiling_cooldown_minutes: 30 → 120`。毎時runに対して初回失敗から2時間は遮断が効くようになる（実測の 17:00〜20:00 の4連続失敗は 17:00 の時点で 3件目の手前なので 20:00 の run が遮断される）。
   - トレードオフ: 収集が停止すると懸賞データの鮮度が落ちる。遮断中は通知（`notify_on_error`）と人手でのセッション再取得を運用に組み込むことが前提。**BOTシグナル増幅（上記）を止める効果の方が大きい**と判断する。
   - 恒久修正（コード・別タスク）: `first_fail_time` を毎回更新する／`last_fail_time` を追加し、「直近失敗から cooldown 以内 かつ count>=limit」で判定する。

3. **ceiling のキーをアカウント粒度にする（コード・別タスク）**
   `applier.apply_for_account` の `context` に `{"key": f"apply:{account_key}"}` を渡す。これで失効垢 zin20120731 の失敗が3回で遮断され、**約50回分のログイン再試行（BOTシグナル）を未然に止められる**。これが今回の実測で最も費用対効果が高い修正。

4. **回復順に session 系を入れる（コード・別タスク）**
   既定 `order` に `session_retry` を含め、validator シグナルにも kind を付けて `_SESSION_MARKERS` 相当の判定を通す。auth 失効に対しては「時間を空けて再試行」ではなく「セッション再取得を促して当該垢をスキップ」が正しい（現行は3回転して毎回失敗するだけなので、リトライを重ねるほどシグナルが増える）。

5. **`max_attempts` は増やさない（3のまま維持）**
   F4 により後半アクションに到達しないという不備はあるが、増やすと BOTシグナル増幅がさらに悪化する。上限を上げる場合は必ず F5（遮断）とセットで行うこと。

6. **config とハードコードの乖離を解消（F6）**
   `retry_empty_collection` / `retry_partial_apply` をコード側で config から読むようにする（現状は設定値を書いても効かないため、運用者が誤解する）。

7. **最低限の可観測性を確保（F1・コード・別タスク）**
   `self.logger` を使って `HealingEvent` を1行ずつ出す（pipeline / attempt / error_kind / action / detail）。今回 retry の実在証明に時系列復元を使わされた分のコストを将来ゼロにできる。

## 未達項目と追跡

- タスク内容3の「48時間稼働後の実測」は**未達**: 導入 2026-09-22 12:52:20 から 37.7時間、apply 最終失敗以降の露出 0 回、collection 修正後の収集run は1回のみ。
- 再測条件: 2026-09-24 09:00 JST 以降の稼働帯（収集 09:00〜21:00、apply 各バッチ）を通過し、導入から48時間（2026-09-24 12:52）を超えた時点。本レポートの解析スクリプトを再実行すれば同一手順で数値が更新できる。
- 追跡タスク: `t_66c14eb4` の子として起票（kensho-qa 宛、本文に再測条件と再実行コマンドを記載）。

## 検証

    $ python3 -m pytest tests/test_self_heal.py -q --no-cov
    18 passed in 57.91s

    $ python3 -m pytest tests/test_guarded_source_arity.py tests/test_self_heal.py -q --no-cov
    23 passed in 43.54s

    $ for f in logs/auto_*.log; do n=$(grep -c "self_heal failed:" "$f"); echo "$f: $n"; done
    logs/auto_20260913.log: 0 … logs/auto_20260921.log: 0
    logs/auto_20260922.log: 21      (1失敗=3行 → 7失敗)
    logs/auto_20260923.log: 75      (1失敗=3行 → 25失敗)
    logs/auto_20260924.log: 0

    $ grep -ho "self_heal failed: [^)]*)" logs/auto_*.log | sort | uniq -c
         64 self_heal failed: apply 0 success 1 errors (attempts=3)

    $ grep -rh "self_heal failed" logs/collect_*.log | sed -E 's/.*self_heal failed: //' | sort | uniq -c
          3 _collect_impl.<locals>.<lambda>() missing 3 required positional arguments: 'out', 'ps', and 'ak' (attempts=3)
          1 _collect_impl.<locals>.guarded_source() got an unexpected keyword argument 'proxy' (attempts=3)

    $ grep -n logger kensho/core/self_heal.py
    312:        logger: Any = None,
    318:        self.logger = logger

    $ grep -rn "ai_assisted" --include=*.py --include=*.yaml .
    ./config.yaml:303:  ai_assisted: false
    ./kensho/core/self_heal.py:173:        "ai_assisted": False,
    ./tests/test_self_heal.py:222:            "self_healing": {"max_attempts": 3, "ai_assisted": True, ...}

    $ cat data/self_heal_state.json
    {"ceilings": {"apply": {"count": 0, "first_fail_time": "2026-09-22T15:06:28.137352"},
                  "collection": {"count": 0, "first_fail_time": "2026-09-23T17:01:53.345701"}},
     "updated": "2026-09-24T00:25:46.363902"}

    $ python3 reports/t_66c14eb4_self_heal_analyzer.py | head -30
    "sh_fail_total": 32, "sh_fail_first": "2026-09-22 15:06:28", "sh_fail_last": "2026-09-23 22:19:25",
    "sh_fail_attempts_values": {"3": 32}, "sh_fail_by_day": {"2026-09-22": 7, "2026-09-23": 25},
    "apply_operation_starts_since_last_failure": 0, "hours_of_observation_since_last_failure": 4.24

    $ python3 reports/t_66c14eb4_attribution_check.py > /dev/null && head -18 reports/t_66c14eb4_attribution_output.json
    "failures": 32, "chain_match_attempts": 22,
    "account_distribution": {"zin20120731": 29, "atushi16": 1, "TankanNotes": 2},
    "attempts_distribution": {"3": 32}, "trace_count_distribution": {"1": 5, "3": 22, "6": 3, "9": 1, "12": 1}

    $ for f in logs/collect_20260923_{17,18,19,20,21}*.log; do echo "$f $(grep -c 'self_heal failed' $f) $(stat -c%s $f)"; done
    logs/collect_20260923_170001.log 2 4129
    logs/collect_20260923_180002.log 2 3963
    logs/collect_20260923_190001.log 2 3963
    logs/collect_20260923_200001.log 2 4323
    logs/collect_20260923_210002.log 0 36989

    $ git log -1 --format="%h %ci %s" 290c480
    290c480 2026-09-23 21:27:04 +0900 fix(scraping): guarded_source 引数不整合による収集全停止を修正 + 回帰テスト

    $ for d in 18 19 20 21 22 23; do echo -n "09-$d "; grep -c "goto failed (attempt" logs/auto_202609$d.log; done
    09-18 18 / 09-19 43 / 09-20 63 / 09-21 36 / 09-22 81 / 09-23 227

成果物（再現用に reports/ 配下へ複製）:

- `reports/t_66c14eb4_self_heal_analyzer.py`（before/after KPI 集計）
- `reports/t_66c14eb4_attribution_check.py`（失敗の垢帰属と retry トレース突き合わせ）
- `reports/t_66c14eb4_analyzer_output.json` / `reports/t_66c14eb4_attribution_output.json`（実行結果）
- `reports/t_66c14eb4_evidence.json`（機械可読ハンドオフ）
