# Skills — 利用可能なスキル

外部AIエージェント（freebuff / Codex / Claude Code 等）でこのリポジトリを作業するときに利用するスキル。

## deepseek-coding
- 用途: DeepSeek V4 でのコード作成
- 補助CLI（要インストール）: `bin/claude-pro`（Pro級タスク）/ `bin/claude-flash`（軽量タスク）
- 備考: AGENTS.md 記載のエイリアス。現状 `bin/` には `kensho-ready-deprecate.sh` のみ存在。
  スクリプトが未配置の場合は本リポジトリのコード編集を通常ツールで行うこと。

## claude-code
- 用途: Claude Code CLI 連携
- 呼び出し: `claude` コマンド（インストール済みの場合）

## 利用ポリシー
- スキルは補助。作業対象・禁止事項は `.agents/instructions.md` を優先
- スキル実行時も `.env` / `data/x_session_*.json` / `.secret-local/` 等の読み取り禁止は継続
