## Proposals 2026-10-04

### Priority: new_proposals (score=100, ready=1, todo=0, running=1)

#### P1: t_8bd5a9a1 — Smithery登録6serversのdescription充実（新規作成）

**実測根拠（2026-10-04 API検証）**:
- Smithery API で `atushi1841/kensho-kaku` 等 6服务器すべての **qualifiedName 確認済み**（登録自体は完了）
- しかし **description=空・iconUrl=null・deploymentUrl=null** のまま → 検索で見つからず可視性ゼロ
- 同パターンは Apify 側で t_e2b43c47（description 0→86）として実測成功済み

**収益ゲート接続**:
1. **買う客層**: Claude Desktop/Cursorで日本ホビーデータ(まんだらけ・駿河屋・TCG価格)を取得するLLM開発者
2. **届くチャネル**: Smithery.ai レジストリ検索
3. **30日成功指標**: description空でないサーバー >= 5/6、Smithery経由external_runs >= 1
4. **再利用資産**: 既存6 MCPサーバー（smithery.yaml は commit 52fcca3 で済）

**検証コマンド**: `curl -s https://api.smithery.ai/servers/atushi1841/kensho-kaku | python3 -c "import json,sys;print(json.load(sys.stdin)['description'])"`

**失敗時代替案**: Smithery API認証不可の場合はGitHub READMEにMCP設定手順＋ストアリンクを追記しmcp.soに手動提出

---

#### P2: t_a7b4b682 — MCPレジストリ一括登録（既存・実行完了済み）

**完了状態（実測）**:
- smithery.yaml 6服务器作成・GitHub push 済み（commit 52fcca3）
- Smithery API で6服务器の qualifiedName 確認
- **残课题**: description空 → 上記 P1 が直ぐに有効化

---

#### P3: t_603f0526 — circuit-breaker-stagnation-detection（ready・worker未着手）

**内容**: data/circuit_state.json + scripts/circuit_breaker.py を作成し、3サイクル停滞で自動trip。
**優先度**: 中（内部監視強化。収益ゲート未接続のため worker の後回し becoming）

---

### 状況サマリ

- **loop_health score**: 100（state file last_run=10-04T22:26、鲜度OK）
- **priority**: new_proposals（ready=1/todo=0/blocked=0/running=1）
- **revenue gate**: external_users 35日連続0、Gumroad売上0（views=2/日）、Apify外部run 18 actors tracked だが external_views=0
- **実行中**: t_a7b4b682（MCPレジストリ登録・worker完了間近）
- **新規提案**: t_8bd5a9a1（Smithery description充実）
- **Gumroad**: views 2→2（前日比0%、target prev+20%未達）、sales 0