# .agents/

`freebuff --trust-agents` フラグで自動読込されるエージェント設定の置き場所。

| ファイル | 役割 |
|---|---|
| `instructions.md` | プロジェクトルールの正本（禁止事項・作業対象・開発コマンド） |
| `skills.md` | 利用するスキルの目次（deepseek-coding, claude-code） |

- `AGENTS.md` と同じ方針。矛盾時は禁止側を優先
- 認証情報（`.env`, `data/x_session_*.json`, `.secret-local/`）はエージェントからは読ませない
- このディレクトリはコミット可（認証情報を含まない）
