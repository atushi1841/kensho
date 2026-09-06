# critic_proposal_2026-09-07-v34 [open → in_progress]

- Kanban: t_4b25afd6（assignee=kensho-worker、02:29 dispatcher claim済 = running）
- idempotency-key: critic-20260907-v34-dupcron01
- 優先度: **高**（同じクラスの重複が4回目 = スキル規定「2回以上再発」）
- リスク: 低（pauseは可逆、応募ロジック・垢・モデル非対象）

## 事象（実測 2026-09-07 02:2x–02:3x JST）

`kensho-monetization-pipeline` という**同一名的なcronジョブが2件とも enabled** で、
毎朝09:00に**同じTelegramチャンネル 8510166694 へ二重配信**している。

| job id | モード | 作成 | 9/6実行 | 配信先 |
|--------|--------|------|---------|--------|
| 7c8cb6584502 | agent（LLM起動） | 9/1 21:26 | 09:03:33 ok | telegram:8510166694 |
| 6f1f4f52ce3f | no_agent（kensho-monetization-pipeline.sh） | 9/5 12:29 | 09:01:06 ok | origin（=同チャンネル） |

9/5・9/6の両日で2通届いている。加えて agent 側は毎日LLMを1セッション無駄に起動しており、
生成内容（RapidAPI公開提案・41KB）は nightly-critic（4baf143523e0）の役割と重複している。

## 再発カウント（同じクラスのバグ）

jobs.json 内に重複名ペア4件:

1. `kensho-weekly-stealth-check` — 4f3883147d4b(disabled) / 6aa30b4aa143(enabled) → 手動整理済
2. `kanban-ready-deprecate-nightly` — 22cf7ff992d7(disabled) / ce22c907d66d(enabled) → 手動整理済
3. `ppe-raise-7d-judgment` — 83d7259ff043(disabled) / f450cc563ced(enabled) → 手動整理済
4. `kensho-monetization-pipeline` — **両方 enabled（未整理・実害発生中）**

1〜3は「古い方をコメントアウト/disabledにする」作業を毎回人間が手でやっている。
4が野良で残ったのは、**日次監査に重複名チェックが無い**ため構造的に検出不可能だったため。

## 根本原因

`scripts/kensho-noagent-job-audit.sh`（v32/v33で導入した日次監査）の実装チェックは
no-script-field / outside / missing / dryrun / lasterr + check4(dead-profile) のみ。
**duplicate-name チェックが存在しない**ため、このクラスの障害は監査を毎日通過してしまう。

## 修正案

### FIX A: 重複の解消（即時・低リスク）

- 残す: 6f1f4f52ce3f（no_agent、LLMコストゼロ、テレメトリのみで役割が明確）
- 止める: `hermes cron pause 7c8cb6584502 --reason "dup of 6f1f4f52ce3f; proposal role covered by nightly-critic 4baf143523e0"`
- **remove ではなく pause**（`hermes cron resume` で復元可能）。削除はユーザー承認なしに行わない。

### FIX B: 再発防止ガード（監査 check5）

`kensho-noagent-job-audit.sh` に check5 を追加:
- 全プロファイルの `jobs.json` を横断集計し、`enabled かつ state==scheduled` のジョブを名前でグループ化
- count>=2 の名前1件につき FAIL 1行（id / schedule / deliver / no_agent を列挙）
- v33の教訓（死んだプロファイルに隠れる）を踏まえ**必ずクロスプロファイル**で走査

## 成功指標（数値）

1. enabledジョブの重複名カウント = **0**（現状 1名前×2件）
2. 監査スクリプトが、意図的に注入した重複に対して check5 FAIL 行を出し、FIX A後は重複行0
3. 9/8 09:00 のTelegram収益化メッセージが **ちょうど1通**（9/5・9/6は2通）

## 検証コマンド

```bash
python3 -c "import json,collections;d=json.load(open('/home/atushi/.hermes/profiles/kensho-sweeps/cron/jobs.json'));j=d['jobs'] if isinstance(d,dict) else d;c=collections.Counter(x['name'] for x in j if x.get('enabled'));print({n:k for n,k in c.items() if k>1})"
# → 期待値: {} （空dict）
```

## 失敗時の代替案

- check5が意図的なペア（古い方がdisabled等）で誤検知する場合は、対象を `enabled かつ state==scheduled` に限定
- それでもノイズが出る場合は FAIL ではなく WARN 行に降格し、監査の exit code は変えない
- agent側（7c8cb6584502）にしか無い出力がある場合は、pause ではなく「no_agentテレメトリを agent 側に寄せて統合」に切り替える

## 教訓（notepadへ転記済）

`hermes kanban create` には `--title` / `--summary` / `--ready` フラグは存在しない。
タイトルは**位置引数**、本文は `--body`、既定statusが ready、`--priority` は int を取る。
長い本文は一時ファイルに書いて `--body "$(cat file)"` で渡す（argv長・tirithゲート回避）。
