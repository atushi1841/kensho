# board-assignees.md — 実在assignee一覧（唯一の真実源）

> 作成: 2026-09-24 (t_81b20406) / 目的: AIエージェントが `kanban_create` / `hermes kanban create`
> を叩く前に参照し、**役割名を発明しない**ようにする。幽霊assignee（実在しないprofile）が作成されると
> dispatcher がそのカードを無言でスキップし、永久に ready 滞留する。

## 実在するassignee（このリスト以外は全て幽霊）

| assignee | 役割 | ON DISK |
|---|---|---|
| `default` | デフォルト | yes |
| `hazard-mcp` | 危険リスクMCP | yes |
| `kensho-critic` | 検証/critic | yes |
| `kensho-qa` | QA検証 | yes |
| `kensho-revenue-qa` | 収益系QA | yes |
| `kensho-revenue-worker` | 収益系worker | yes |
| `kensho-sweeps` | スイープ（Kensho全体） | yes |
| `kensho-worker` | 一般worker | yes |
| `line-stamp` | LINEスタンプ | yes |
| `tai` | taiプロファイル | yes |

## 過去の幽霊assignee → 実在profileマッピング（参照用）

| 幽霊assignee（使用禁止） | 実在profileへ |
|---|---|
| `critic-a` | `kensho-critic` または `kensho-qa` |
| `worker` | `kensho-worker` |
| `orchestrator` | `kensho-revenue-worker` |
| `researcher-a` | `kensho-revenue-worker` |

## ルール

1. カード作成前の必須ステップ: `hermes profile list`（または本ファイル）と照合し、
   assignee が上表に含まれることを確認する。
2. 役割名（"critic" / "worker" / "orchestrator" / "researcher" 等）を**発明しない**。
   その役割に該当する実在profileを**本ファイルから選ぶ**。
3. 未知のassigneeなら `kanban_create` を呼ぶ前に `kanban_block(reason=...)` か
   `kanban_comment` で報告し、実在profileへ付替えます。
4. 本ファイルに追加する新規profileは `hermes profile list` の出力と照合し、
   ON DISK=yes のものに限る。

## 検証コマンド（1行）

```sh
hermes kanban --board kensho-ai-team assignees | grep -c ' no '   # → 0 が成功
```

（2026-09-24 現在: 0。幽霊assignee 0件・実在10プロファイルのみ）