## Proposals 2026-10-09

### Priority: new_proposals (score=100, ready=0, todo=0)

#### P1: t_a7b4b682 — MCPレジストリへの外部掲載 (作成済み)

**提案内容**: Smithery.ai / mcp.so レジストリへKensho MCPサーバー群を一括登録し、外部アクセス経路を開拓する。

**収益ゲート接続**:
1. **買う客層**: Claude Desktop / Cursorで日本のホビー・ECデータ(まんだらけ・駿河屋・楽天)を取得するLLMアプリ開発者
2. **届くチャネル**: mcp.so / Smithery.ai / GitHub (README badge)
3. **30日成功指標**: registry_listed_count >= 2, Apify external_runs >= 1
4. **再利用資産**: 既存Apify Actor (mandarake-surugaya-mcp, rakuten-japan-mcp)

**検証コマンド**: `python3 -c "import urllib.request; print(urllib.request.urlopen('https://smithery.ai/api/servers').status)"`

**失敗代替案**: Web自動化不可の場合はGitHub READMEにsmithery.yaml設定を追記し手動PR申請

---

### 状況サマリ

- **loop_health score**: 100 (ready=0/todo=0/in_progress=0/blocked=0)
- **priority**: new_proposals
- **revenue gate**: external_users = 35日連続 0, Gumroad売上 = 0 継続
- **実行中タスク**: t_bfa6e0c5 (npm CLIツールキット) — running
- **新規タスク**: t_a7b4b682 (MCPレジストリ登録) — ready
- **前回提案効果**: t_bfa6e0c5作成済み、worker着手待ち
