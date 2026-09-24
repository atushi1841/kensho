# Critic 追加レポート 2026-09-23: 幽霊assignee永久滞留の修復

実行ジョブ: nightly-critic (4baf143523e0) / 実行時刻 2026-09-23 19:2x JST
トリガ: monitor差分 `ready=10→11, blocked=1→0` を起点に、ready滞留の中身を実測。

## 1. 発見（実測）
```
$ hermes kanban --board kensho-ai-team assignees
critic-a              no        ready=1, todo=3
orchestrator          no        ready=1
researcher-a          no        ready=1
worker                no        ready=2
（他は ON DISK=yes）
$ hermes profile list
default, hazard-mcp, kensho-critic, kensho-qa, kensho-revenue-qa,
kensho-revenue-worker, kensho-sweeps, kensho-worker, line-stamp, tai
```
→ `critic-a` / `worker` / `orchestrator` / `researcher-a` は実在プロファイルではない。
dispatcherは未知assigneeのカードを無言スキップするため、**計8カード（ready5 + todo3）が永久滞留**していた。

対象カード（created_by=worker, 作成 9/19〜9/23）:
t_fa046d3a, t_66c14eb4, t_3609e866, t_e97fd8f8, t_47f2015c, t_0b949bda, t_eca89f41, t_96c94435

## 2. 修復（実施済み）
assigneeの付け替え（`hermes kanban reassign <id> <profile> --reason ...`）＋各カードにコメント記録:

| task | 旧 | 新 |
|---|---|---|
| t_fa046d3a 自律稼働工場化 実装 | critic-a | kensho-worker |
| t_66c14eb4 self_heal実効果検証 | critic-a | kensho-qa |
| t_3609e866 1週間モニタリング | critic-a | kensho-qa |
| t_e97fd8f8 KPI再チェック実装 | critic-a | kensho-worker |
| t_47f2015c Redditパイプライン(GO) | orchestrator | kensho-revenue-worker |
| t_0b949bda AIデータジャーナリズム | researcher-a | kensho-revenue-worker |
| t_eca89f41 Outcome Review導入 | worker | kensho-worker |
| t_96c94435 サーキットブレーカー導入 | worker | kensho-worker |

検証（修復後）:
```
$ hermes kanban --board kensho-ai-team assignees | grep -c ' no '
0
```
付替え直後に t_eca89f41(kensho-worker) と t_47f2015c 系がdispatcherにclaimされ running 化 → 滞留復活を実測確認。

## 3. 併発所見: protocol violation 多発
```
$ sqlite: select count(*) from task_runs where error like '%protocol violation%'
323        # 全期間
本日(09-23) 75件（08時4, 10時4, 11時3, 12時3, 09時2, 13時2, 14時2, …）
```
- 稼働中dispatcher spawnの env には `HERMES_KANBAN_TASK` が**設定されている**（`tr '\0' '\n' </proc/<pid>/environ`）→ QA申し送りの「env欠落」説は否定的。
- 主因候補は (a) max_iterations 90/90 到達、(b) kanban stop nudge 予算(2回)枯渇後の clean exit。
- 対策カード: **t_02a5afc4**（成功指標: 9/24のcrash ≤10件）。

## 4. 本日作成した提案カード
- t_02a5afc4 `[ループ衛生] worker終端kanban呼出しの強制`（assignee: kensho-worker, priority 2）
- t_81b20406 `[ループ衛生] 幽霊assignee検出ガード`（assignee: kensho-worker, priority 1）

## 5. 未確認（申し送り）
- SOCKS5 1084/1087/1089 は WSL→127.0.0.1 および 172.26.80.1 の両方で code=000。WSL→Windows側FW/portproxyの可能性があり**proxy死と断定不可**。プロジェクト内チェッカーでの実測が必要（誤報回避のため未報告）。
- t_ddb7764a は【要ユーザー対応】9/27ゲート維持（データ依存）。
