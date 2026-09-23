# t_47f2015c 検証記録 — Reddit自動投稿カードの重複却下

- 対象タスク: `t_47f2015c`（Redditアカウント育成・自動投稿パイプライン構築 (GO)）
- 判定: `t_47f2015c` は重複カードにつき却下（クローズ）。以降のReddit案件は正規カードに集約する
- 実施: kensho-sweeps / 2026-09-23 20:40-21:10 JST（読み取りのみ・本番パイプラインとゲートは未変更）

## t_47f2015c を却下する理由

1. `t_47f2015c` は `created_by=worker` の自動生成カードで、ユーザー作成の正規カード
   （Reddit新垢＋週1価値提供投稿パイプライン）と同一テーマ。同一テーマを2枚同時に走らせると
   二重実装・二重投稿の危険がある（WIP規律違反）。
2. `t_47f2015c` 本文の前提ファイルが存在しない。本文は「`reddit_cdp_submit_v2.js` の実装・検証」を
   作業項目2に挙げるが、リポジトリ直下に当該ファイルは無く、実体は `data/reddit/cdp_submit_v2.js`
   として 2026-09-07 に作成済み。すなわち項目2は既に完了している。
3. `t_47f2015c` の作業項目3「Karma蓄積＝コメント先乗りの自動化」は既存の設計決定に反する。
   `reports/2026-09-07-reddit-newaccount-research.md` §5.2 が
   「Karma形成（コメント/vote）は自動化しない（ユーザーが10分/日で手動）」と明記し、
   その理由は「rapid-fire＝BOT判定の最速トリガー」。旧垢 Significant-House109 の垢級403を
   再発させる構造変更にあたるため、worker判断では実装しない。
4. `t_47f2015c` の「(GO)」表記は作成者=worker の自己申告（`created_by=worker`）。
   ユーザーのGOはTelegram経由のみ有効であり、これを承認と見なさない。

## verification_evidence

2026-09-23 20:40-21:10 JST に実測した。t_47f2015c の判定根拠はすべて読み取り操作のみ。

```
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/reddit-gate-check.sh; echo "exit=$?"
== reddit gate check 2026-09-23 20:44:16 JST ==
PASS G0: cookie ok (11 entries, reddit_session=True csrf=True)
FAIL G1: warm-up not finished (today=2026-09-23 resume_from=2026-09-28)
FAIL G2: no go.flag - user must enable phone tethering then run: touch /mnt/d/Project2/kensho/data/reddit/go.flag
FAIL G3: post_queue.json missing
PASS G4: identity ok (u/sabotenJAL == expected u/sabotenJAL)
FAIL G5: account too young (sabotenJAL age_days=16 < 30)
PASS G6: submitter present (/mnt/d/Project2/kensho/data/reddit/cdp_submit_v2.js)
--
GATES: FAIL (4 gate(s) blocked) -> DO NOT POST
exit=1
```

```
$ ls -la /mnt/d/Project2/kensho/reddit_cdp_submit_v2.js
ls: cannot access 'reddit_cdp_submit_v2.js': No such file or directory

$ ls -la /mnt/d/Project2/kensho/data/reddit/
cookie_new.json (9/7 07:37) / cdp_submit_v2.js (9/7 09:06) / expected_account.txt (9/7 15:03 -> "sabotenJAL")
go.flag: 無し / post_queue.json: 無し
```

```
$ head -5 /home/atushi/.hermes/profiles/kensho-sweeps/scripts/reddit-gate-check.sh
# Reddit weekly post gate checker (kensho / u/sabotenJAL -- 2026-09-07ユーザー確定、hbomaxは無関係垢)
```

```
$ hermes cron list  (抜粋)
9689ecb38792  reddit-sabotenJAL-weekly  "0 10 * * 1"  state=paused  (2026-09-07 09:05 から停止のまま)
```

## t_47f2015c 検証で確定した事実（誤りの訂正を含む）

- 運転対象垢は **u/sabotenJAL** で確定済み（`expected_account.txt` とゲートのヘッダに
  「2026-09-07ユーザー確定、hbomaxは無関係垢」と明記）。9/7時点で報告された
  「identity mismatch」は v50 修正でハードコードfallbackが削除され解消、実測でも **G4 は PASS**。
- 投稿はゲートで機械的に禁止されており、t_47f2015c から投稿・コメントは一切実行していない。
- 残ブロッカーは4点：G1(2026-09-28待ち) / G2(ユーザーのテザリングON＋go.flag) /
  G3(初回投稿の下書き未作成) / G5(垢年齢30日以上＝最早 **2026-10-07**)。
- G1(9/28) と G5(10/07) は矛盾しており、実効的な再開可能日は 10/07。要判断事項として正規カード側へ記録した。

## t_47f2015c の再発防止

- Reddit関連の新規カードは起票しない（既存の正規カードに集約）。
- 投稿系cron `reddit-sabotenJAL-weekly` はゲートPASSまで paused を維持する。
