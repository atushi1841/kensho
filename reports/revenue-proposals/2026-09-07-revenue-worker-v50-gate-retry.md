# revenue-worker v50 — reddit-gate G4 誤診修正（retry+エラー分類）（2026-09-07 15:0x JST）

- ジョブ: nightly-worker `5e8ec4984bba` / run 14:45 JST
- タスク: **t_cc939def**（worker自己検出: G4が一時的ネットワークERRを'cookie失効'と誤診 → retry+分類）
- 優先度: 高（自動復旧阻害系 — 誤診で「cookie再エクスポート要」と誤誘導し、ユーザー対応を浪費させる）

## 0. 健康度とタスク選択の根拠

`loop_health.sh` 実測: score=95 / ready=0 / blocked=0 / in_progress=0 / done=294 /
priority=new_proposals / streak=0 / skip_fast=false。

ready=0・blocked=0 で着手候補ゼロ。monitor差分で wip 2→0・done 291→294（run 231系が完了）を確認。
ただし **skillの「実装中のエラー記録」ルール** に該当するバグを自前で2回実測していたため、
新規タスク t_cc939def を作成（idempotency-key=worker-20260907-v50-gate-retry）して1件だけ実装。

## 1. 発見したバグ（エビデンス）

同一cookie・同一スクリプトで G4 の結果が揺れた:

| 時刻 | 結果 | 出力 |
|------|------|------|
| 14:48 | FAIL G4 | `identity lookup failed (ERR auth URLError ) - cookie may be expired` |
| 14:52 | PASS G4 | `identity ok (u/sabotenJAL == expected u/sabotenJAL)` |

→ urllib の一時的失敗（URLError）を「cookie失効」と断定する誤診。
reddit は 403/ブロックを間欠的に返す（同日単独curlでも old.reddit 302 / www 403 を実測）。
cron STEP0ゲートがこの誤診を出すと、**cookieが生きているのに「再エクスポートせよ」と誤誘導**し、
warm-up再開（9/28以降）の判断自体が狂う。

さらに潜在バグ2件をコードレビューで発見:
1. `EXPECTED="hbomax"` ハードコードフォールバック → expected_account.txt が消えると
   無関係垢名で照合し、不一致FAILにはなるが「身元確定なしで走る」設計欠陥
2. about.json（karma取得）失敗が G4 に化ける → 身元は正しいのに「cookie問題」表示

## 2. 実装内容

変更ファイル: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/reddit-gate-check.sh`（G4/G5セクション）

1. **3回リトライ+バックオフ**（2s/5s/8s）で `/api/me.json` を呼ぶ
2. **エラー分類**:
   - `AUTHFAIL`（HTTP 401/403）→ 「cookie失効 or 垢ブロック、再エクスポート要」
   - `TRANSIENT`（3回とも失敗）→ 「**cookie問題ではない**。後で再実行」
   - `WRONGACCOUNT` → 従来どおり不一致ブロック
   - `ABOUTFAIL` → G4=PASS（身元OK）、G5=karma取得失敗として分離
3. **ハードコードフォールバック削除**: expected_account.txt 不在/空なら G4 即FAIL（身元推測禁止）
4. 出力はASCII-only維持（confusable_textフック教訓 2026-09-05）

ロールバック: profile git `git revert`（commit 0b8df48 の直後、本修正コミット1つで戻る）

## 3. 検証（全パス実測）

| ケース | 操作 | 期待 | 実測 |
|--------|------|------|------|
| T0 正常 | 現状そのまま | PASS G4 | `PASS G4: identity ok (u/sabotenJAL == expected u/sabotenJAL)` ✅ |
| T1 ファイル不在 | expected_account.txt リネーム | FAIL（推測しない） | `FAIL G4: expected_account.txt missing - cannot bind identity` ✅ |
| T2 不一致 | expected=hbomax に書換 | WRONGACCOUNT | `FAIL G4: identity mismatch (WRONGACCOUNT sabotenJAL expected=hbomax)` ✅ |
| T3 一時的失敗 | URLを127.0.0.1:9へ置換した複製で実行 | TRANSIENT（失効と区別） | `FAIL G4: network transient after 3 tries (TRANSIENT URLError ) - NOT a cookie problem` ✅ |
| 構文 | `bash -n` | OK | SYNTAX_OK ✅ |
| 全体 | 実走 | GATES FAIL（G1/G2/G3/G5が正しく塞いでいる） | `GATES: FAIL (4 gate(s) blocked) -> DO NOT POST` / exit 1 ✅ |

T2/T3後は expected_account.txt を `sabotenJAL` に復元済み（cat で確認）。

## 4. 副次発見（申し送り）

- **垢の身元問題は解消**: 14:42:47 に expected_account.txt=sabotenJAL が作成されており（ユーザー確定と推定）、
  G4は PASS。残ブロッカーは G1 warm-up（9/28まで）/ G2 go.flag / G3 queue / G5 垢年齢30日未満 の4つ。
  → 「【要ユーザー対応】垢取り違え」は **クローズ可**。ただし MEMORY.md 19行目はまだ
  「新垢u/hbomax」と記載しており実態（u/sabotenJAL, karma=1, created 9/6 22:03 UTC）と不一致 →
  critic/ユーザーへ申し送り（memoryは他セッション共有のため本workerでは未編集）。
- cron 9689ecb38792 は paused 維持が正しい（resume 9/28以降、G5垢年齢も 10/6 以降でないとPASSしない）。
- `hermes cron list` の grep に 9689ecb38792 が出なかった（別プロファイル管理の可能性）。
  状態変更は行っていない。

## 5. Reflexion

```json
{"self_review":{"what_was_done":"reddit-gate-check.sh G4の誤診バグ（一時的ネットワークERRをcookie失効と断定）を修正。3回リトライ+AUTHFAIL/TRANSIENT/WRONGACCOUNT/ABOUTFAILの4分類、hbomaxハードコードフォールバック削除。T0-T3の4ケースを実測検証しprofile gitへコミット。","what_went_well":["同じrun内で2回観測された揺れをその場でバグ化・タスク化できた（skillの『同じエラー2回=高優先』ルールの実践）","T3検証で実URLを叩かずにローカル宛URL置換複製を使い、redditレート制限を消費せず再現した","身元問題がユーザーにより解決済み（expected_account.txt=sabotenJAL）であることをgate再走で確認し、notepadの『要ユーザー対応』を正しくクローズ化"],"what_could_improve":["AUTHFAIL(401/403)分岐は実データで直接再現できていない（有効cookieで403を出せないため）。ロジック共通なので許容範囲だが、将来cookie失効時に初めて実証される","MEMORY.mdの不整合は発見したが他セッション共有領域のため編集を見送った。critic経由の確定に回す"],"mistakes_or_risks":["リトライで最悪 3回x30sタイムアウト+バックオフ=約100sゲートが遅延する。cron STEP0は15分セッションなので許容範囲だが、G4失敗時のみ遅延する設計","T2検証中に一瞬 expected=hbomax 状態が存在した（即復元済み、投稿cronはpausedなので実害ゼロ）"],"learned":"外部APIゲートは『失敗の種類』を必ず分類して報告すること。1つのFAILメッセージに『失効・不一致・ネットワーク』を混ぜると、ユーザーに誤った再作業（再エクスポート）を要求する。エラー分類=ユーザー対応コストの品質。","confidence":9,"verification_evidence":"T0: PASS G4 identity ok (u/sabotenJAL) 15:03実走 / T1: FAIL G4 expected_account.txt missing 15:04実走 / T2: FAIL G4 WRONGACCOUNT sabotenJAL expected=hbomax 15:04実走 / T3: FAIL G4 network transient after 3 tries 15:05実走 / bash -n SYNTAX_OK / 全体 exit 1 (GATES FAIL 4) / git commit 0b8df48+修正コミット, status --porcelain scripts/ = 0行"}}
```
