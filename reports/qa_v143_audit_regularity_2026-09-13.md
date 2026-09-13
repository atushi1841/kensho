# QA検証レポート — v143 audit_bot_safety.py 検査6「日跨ぎ規則性」独立検証

- QAカード: t_321e23e6（親: t_32c2723a）
- 対象コミット: 5938330 (main, push済み / origin b7f2ff0..5938330)
- 検証日時: 2026-09-13 17:05〜17:12 JST（run 450）
- 検証者: kensho-revenue-qa（読み取りのみ、ソース改修なし）
- **最終判定: PASS（7/7項目）**

## 手順1・2 — 受け入れコマンド＋検出行の実測一致 ✅

```
$ cd /mnt/d/Project2/kensho && python3 scripts/audit_bot_safety.py 2026-09-12 | grep -c 正規性
2
$ echo $?   # 終了コード
1
```

出力全文:
```
[audit_bot_safety] 2026-09-12: 2件のBOTシグナル検出
  [正規性] 2026-09-12 atushi16 初動stdev13.9分(<30)・件数CV0.10(<0.15) (直近7日 初動8時台中心・件数mean104 → 規則的パターン=検出リスク、batch時刻ジッタ改修は別カードでGO提案)
  [正規性] 2026-09-12 zin20120731 初動stdev17.3分(<30) (直近7日 初動8時台中心・件数mean97 → 規則的パターン=検出リスク、batch時刻ジッタ改修は別カードでGO提案)
```

- 終了コード=1 ✅（信号あり=要確認、cron monitor契約通り）
- atushi16: 初動stdev **13.9分**・件数CV **0.10**・mean104 ✅
- zin20120731: 初動stdev **17.3分**・mean97（CV0.23は閾値外のため件数項非表示＝仕様通り）✅
- ⚠ 軽微な指摘（判定に影響なし）: QAカード本文は照合先を「research-20260913.md 実測表」と表記だが、数値の実在先は **reports/critic_v143_regularity_audit_2026-09-13.md:10-11**（atushi16=13.9/104/0.10、zin20120731=17.3/97/0.23）。research-20260913.mdは提案根拠（時間正規性シグナル論）の側で、13.9/17.3の実測表は含まれない。カードの参照ファイル表記の誤記として記録。

## 手順3 — 回帰ゼロ（旧版 vs 新版、同一data条件で比較）✅

`git show 5938330~1:scripts/audit_bot_safety.py > /tmp/orig_v143.py` を取得し、`__file__` 基準の相対パス解決（AUDIT_PATH/CONFIG_PATH）を維持するため /tmp/qa143/{scripts,data} に sandbox を組んで旧版を実行（config.yaml は symlink で同一実物参照、audit.jsonl 5,880,084B を同一コピー）。

2026-08-27:
```
旧版: [audit_bot_safety] 2026-08-27: BOTシグナルなし (深夜ゼロ・連続なし・単独アクション)  exit=0
新版: [audit_bot_safety] 2026-08-27: BOTシグナルなし (深夜ゼロ・連続なし・単独アクション)  exit=0
$ diff → 0行（完全一致）
```

2026-09-12（新版の正規性2行を除く差分有無）:
```
旧版: [audit_bot_safety] 2026-09-12: BOTシグナルなし ...  exit=0
新版: 2件のBOTシグナル検出 + [正規性]2行  exit=1
```
新版出力から正規性行のみ除去したものと旧版出力を diff → ヘッダ件数行（「なし」→「2件検出」）以外の差異なし。**既存検査1〜5の出力は完全に不変**で、差分は検査6追加による意図的な検出増のみ。回帰ゼロ確認 ✅（実施者の2026-08-27/09-12突合済み報告と独立再現で一致）。

## 手順4 — pytest 全suite 安定化 ✅

```
$ python3 -m pytest -q
================== 568 passed, 5 skipped in 79.11s (0:01:19) ===================
```

- フォーマット**後**のHEAD（commit 5938330）で全suite再走 → 568 passed / 5 skipped。実施者報告（フォーマット前568 passed＋フォーマット後新規8件のみ再走）の未実施分を本QAで確定。
- 新規8件単体も再確認: `pytest tests/test_audit_bot_safety_regularity.py -q` → **8 passed** ✅

## 手順5 — mypy 新規起因0 ✅

```
$ python3 -m mypy scripts/audit_bot_safety.py   # 現場の mypy.ini（strict, ignore_missing_imports）適用
scripts/audit_bot_safety.py:161: error: Returning Any from function declared to return "dict[str, list[str]]"  [no-any-return]
scripts/audit_bot_safety.py:230: error: Need type annotation for "night"  [var-annotated]
scripts/audit_bot_safety.py:266: error: Need type annotation for "owner_follows"  [var-annotated]
scripts/audit_bot_safety.py:275: error: Need type annotation for "hourly"  [var-annotated]
Found 4 errors in 1 file
```

同一条件で旧版（/tmp/orig_v143.py、scripts配下sandbox）を計測 → 4件（no-any-return + night/owner_follows/hourly var-annotated、行番号43/151/187/196）。**HEAD側の4件と内容同一・行番号シフトのみ＝新規起因0** ✅（mypy.ini は exclude=scripts/ だが明示パス指定で検査される。pyprojectの[tool.mypy]ではなく mypy.ini が優先される点も双方同条件で比較済み）。

## 手順6 — --state 既報抑制契約 ✅

[正規性] 行は `f"[正規性] {date_s} {acct} ..."`（scripts/audit_bot_safety.py:134）で date_s を含む → state の日付キー {date_s: [lines]} での既報抑制が機能する設計。実測:

```
$ unlink data/.audit_bot_safety_state.json   # 掃除後の初回相当（検証前に cp -p でバックアップ済み）
$ python3 scripts/audit_bot_safety.py --today --state
[audit_bot_safety] 2026-09-13: 2件のBOTシグナル検出
  [正規性] 2026-09-13 atushi16 初動stdev13.9分(<30) (...件数mean101...)
  [正規性] 2026-09-13 zin20120731 初動stdev17.4分(<30)・件数CV0.03(<0.15) (...件数mean106...)
RUN1_EXIT=1
$ python3 scripts/audit_bot_safety.py --today --state
[audit_bot_safety] 2026-09-13: BOTシグナルなし (深夜ゼロ・連続なし・単独アクション)
RUN2_EXIT=0
```

- 1回目=正規性2行出力（exit 1）→ 2回目=同一行が抑制され「BOTシグナルなし」（exit 0）✅ 当日重複出力なし。
- 深夜窓(00:00-07:00)外執行のため他シグナルは不出力（カード記載の前提通り、正規性抑制のみでの確認）。
- 検証後はバックアップから state を復元（cp -p、mtime 17:05 の実物内容＝2026-09-13既報2行を復元済み）。現行cron monitorの既報情報に欠損なし。
- 参考: 当日(--today)の数値(atushi16 13.9/mean101、zin20120731 17.4/CV0.03/mean106)は09-12確定日と異なるが、これは7日窓＋当日データの進行による正常な差分（実装の誤りではない）。

## 手順7 — スコープ遵守 ✅

```
$ git diff 5938330~1 5938330 --stat
 reports/critic_implement_2026-09-13_v143.md        |  68 +++++++++++
 reports/critic_v143_regularity_audit_2026-09-13.md |  38 ++++++
 scripts/audit_bot_safety.py                        |  82 +++++++++++++
 tests/test_audit_bot_safety_regularity.py          | 133 +++++++++++++++++++++
 4 files changed, 321 insertions(+)
```

- 変更は監査スクリプト・新規テスト・レポート2件のみ。**config.yaml・応募ロジック（application/・kensho_apply_single.py等）非改修** ✅（純粋な追加のみ、既存行の削除0）。
- 閾値 REGULARITY_START_STDEV_MIN=30 / REGULARITY_COUNT_CV=0.15 が定数化され、読み取り専用（state/audit.jsonlへ書込みなし）であることをdiff確認。

## 申し送り（重大なし）

1. （軽微）QAカード/実装レポートの参照先「research-20260913.md 実測表」は誤記。正: critic_v143_regularity_audit_2026-09-13.md。次カード起票時に表記を直す程度、コード動作に影響なし。
2. 検出型对策（batch時刻ジッタ改修）は実施者報告通り**別カードでGO提案待ち**。atushi16/zin20120731 の初動stdev<30分が正規性シグナルとして毎日出力され続けるため、対策カード未着手なら monitor の既報抑制に依存する運用が継続する（state掃除で再報が上がる設計動作は確認済み）。

## 結論

**PASS**。受け入れ条件（exit=1・正規性2行・数値一致）、回帰ゼロ（既存5検査出力不変）、全suite 568 passed/5 skipped、mypy新規起因0、--state契約、スコープ遵守の全項目を独立再実測で確認。ソース改修なし（読み取りのみ）。git作業ツリーはレポート1ファイル追加の状態（pushはQA運用通り未実施、commitのみ）。
