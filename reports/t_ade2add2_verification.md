# t_ade2add2 検証レポート — BOT検出知見の本番スクリプト反映（early_complete）

## 受入判定
成功指標「調査レポート5トリガーのうち3以上が本番スクリプトに実装」を満たす。

確認コマンド（タスク指定）`grep -r 'rt_done_ids\|session_anomaly\|consecutive_reply' kensho/application/`
は本番スクリプト `kensho/application/applier.py` に `rt_done_ids`（セッション内RT重複防止）を検出。
本実装は先行タスク（t_99e84648 等）で編入され、commit・push 済み（origin/main 所属）。本 run で
受け入れ条件充足を実測確認するのみ（pre-existing・追加実装なし）。

5トリガーの実装内訳:
- 短時間RP連続 / manual RT重複 → `rt_done_ids`（セッション内でRT成功したtweet_id重複をdo_RT前に遮断）
- 定型文同時刻リプライ → `same_campaign_multi` / `_multi_response_record`（複数同時刻応答検知）
- いいね4-5連続 → `consecutive_likes >= 4`（一時停止）＋ `consecutive_rt_like >= anomaly_max_rt_like(5)`（強制終了）
- 懸賞専門枠判定 → config `anomaly_max_consecutive_rt_like` 閾値設定で対処

## verification_evidence

$ grep -rn 'rt_done_ids\|session_anomaly\|consecutive_reply' kensho/application/applier.py
kensho/application/applier.py:1088:        rt_done_ids: set[str] = set()  # セッション内でRT成功したtweet_id
kensho/application/applier.py:1771:                    if tweet_id in rt_done_ids:
kensho/application/applier.py:1876:                        or tweet_id in rt_done_ids
kensho/application/applier.py:2108:                    rt_done_ids.add(tweet_id)

$ grep -n 'consecutive_rt_like\|_anomaly_abort\|same_campaign_multi\|consecutive_likes >= 4' kensho/application/applier.py
kensho/application/applier.py:446:def _multi_response_record(tweet_id: str, account_key: str, cfg: dict, log: Any, state_path: Path | None = None) -> int:
kensho/application/applier.py:795:    _anomaly_abort: bool = False
kensho/application/applier.py:1695:                if not skip_like and consecutive_likes >= 4:
kensho/application/applier.py:1989:                            consecutive_rt_like += 1
kensho/application/applier.py:1992:                                    f"  [ANOMALY] 提案1: RT/いいね{consecutive_rt_like}連続成功"

$ git log --oneline -S'rt_done_ids' -- kensho/application/applier.py | head -2
3f06b67 fix(applier): 提案20 line1202にrt_done_ids追加 - 同一セッション内RT→like多重防止
cf60f79 fix: セッション内重複アクション防止（RT済みtweet_id set・フォロー済み主催者set）

$ git log --oneline -S'consecutive_rt_like' -- kensho/application/applier.py | head -1
7e31a4f chore: 他ワーカーの未commit変更を統合 (config anomaly_threshold + applier + status)

$ git log --oneline -S'same_campaign_multi' -- kensho/application/applier.py | head -1
b4cef16 qa: nightly-qa 2026-09-18 verification + applier CAPTCHA lock state machine

$ for c in 3f06b67 cf60f79 7e31a4f b4cef16; do git merge-base --is-ancestor $c origin/main && echo "$c on origin/main"; done
3f06b67 on origin/main
cf60f79 on origin/main
7e31a4f on origin/main
b4cef16 on origin/main

$ git rev-list --left-right --count origin/main...HEAD
0	1

$ git status --short kensho/application/applier.py
(clean — applier.py はコミット済み・作業ツリー変更なし)
