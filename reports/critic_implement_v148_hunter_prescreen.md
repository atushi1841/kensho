# critic v148: 非API収益hunter事前スクリーニング強化 — 実装記録 (t_df0bdb4f)

- 対象: kensho-non-api-revenue-hunter.py のみ（応募パイプライン・config.yaml 非干渉）
- 根拠: 直近30件のworker完了summaryで却下27件=90%。判定がhunter側に無くworkerへ回されていた。

## 変更内容

quality_gate() にカード作成前の軽量事前スクリーニングを追加（LLM不使用・HTTP GETのみ）:

1. `oss_title_only`（ルール2相当・HTTP不要）: タイトルが Show HN/launch HN + OSS/個人開発語彙
   （my/toy/hobby/simple/open-source/cli/library等）のみ、かつ収益語（paid/pricing/subscription/
   API/dataset等、日本語含む）がタイトル・本文にゼロ → 即スキップ。収益語が1つでもあれば通過
   （見逃し防止）。
2. `gh_oss_free`（ルール1相当・HTTP要）: GitHub直リンク抽出（badge/img誤抽出ガード付き）→
   api.github.com で stars<200 かつ license∈{MIT, Apache-2.0} かつ homepage無し or /pricing
   が404/410 → 『OSS無料配布』としてスキップ。200/30x等は料金ページ有りとして通過。
   ネットワーク障害・ステータス不明・API予算超過は fail-open（通過）で誤判定防止。
   GitHub APIは1実行8件上限+キャッシュで匿名60回/h枠を消費抑制。
3. 観測性: gate_stats に oss_title_only / gh_oss_free を追加、レポートの gate_breakdown・
   「pre-screenスキップ (v148)」集計行・品質ゲート説明節へ反映。

実行順序: score_low → oss_title_only（HTTP不要なので最前）→ wrapper_free → no_monetization →
gh_oss_free（monetization通過後のみHTTP参照、コスト抑制）→ cap_reached。

## テスト

tests/test_non_api_revenue_hunter_gate.py に TestPreScreenTitleRule 4件 +
TestPreScreenGithubOss 8件（低starsスキップ/pricing 200通過/high stars通過/
network failure fail-open/pricing timeout fail-open/非GitHub未参照/ref抽出/b定数）追加。
既存 test_high_score_wrapper_not_skipped は prescreen の network 参照をモックするよう更新。

## 適用禁止領域の遵守

kensho_collect.py / kensho_apply_single.py / kensho_cron_worker.py / config.yaml への変更なし
（git diff --stat で hunter 2ファイルのみ確認済み）。cron実行経路（kensho-sweepsプロファイル
scripts/）へ同期済み（md5一致）。

## verification_evidence

（t_df0bdb4f 実装検証：pytest回帰 + liveスクリプト実HTTP + プロファイルmd5同期）

```
$ cd /mnt/d/Project2/kensho && python3 -m pytest tests/test_non_api_revenue_hunter_gate.py tests/test_collector.py -q -p no:cacheprovider --no-cov
tests/test_collector.py ................................................ [100%]

============================= 85 passed in 16.96s ==============================
```

（hunterゲート単体=37 passed、既存回帰含む全パス）

```
$ python3 /tmp/v148_prescreen_check.py
dsnitch: None
toy_cli: ('oss_title_only', '(pre-screen) Show HN+OSS/個人語彙のみ (収益語ゼロ) でスキップ')
paid_saas: None
httpx: None
```

```
$ python3 /tmp/v148_ghmeta.py
httpx meta: {'stars': 15477, 'license': 'BSD-3-Clause', 'homepage': 'https://www.python-httpx.org/'}
dsnitch meta: {'stars': 9, 'license': 'GPL-3.0', 'homepage': ''}
```

（実HTTP検証: toy_cli=ルール1で即スキップ、paid_saas=収益語ありで通過=過剰フィルタ無し、
httpx=stars15477≥200のため通過、dsnitch(stars9)=licenseがGPL-3.0のためpermissive判定外で通過
— permissive license条件どおりの挙動。ゲート網羅は部分的である点を実測で確認: 直近却下3件の
うちタイトルが「simple」等でルール1に_hitするPushie型はカード化前に止まるが、AttaLambda
(Show HN: ...a language where types...)・Nari (High accuracy, low latency) のようにOSS/個人
語彙をタイトルに持たず、かつhunterカードURLがGitHub直リンクでなく自前ドメインの案件は
今回ゲートでは捕捉不能（stars判定はGitHub URL必須）。従って却下率90%→60%未満の成否は
7日後の検証コマンド実測で判定する）

```
$ md5sum /mnt/d/Project2/kensho/kensho-non-api-revenue-hunter.py /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-non-api-revenue-hunter.py
1c770502ff7b25f839486849a6b8bcb1  /mnt/d/Project2/kensho/kensho-non-api-revenue-hunter.py
1c770502ff7b25f839486849a6b8bcb1  /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-non-api-revenue-hunter.py
```

```
$ ruff check kensho-non-api-revenue-hunter.py tests/test_non_api_revenue_hunter_gate.py
All checks passed!
```

## 成功指標の測定予定

- worker却下率 90%→60%未満: 実装7日後にカード本文の検証コマンドで測定
- hunterスキップログ1日1件以上: 次回のhunter cron実行レポート（gate_breakdown）で観測
