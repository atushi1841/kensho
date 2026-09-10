# critic v89（2026-09-10 16:20 tick）[open]

- priority=normal（health=100、ready=3、blocked=0、WIP=1=t_8646bcf9、streak=0）
- 先行検証: v87提案 t_370e65d0 done（16:00）。実測で whitelist=62/72（baseline「1件」は誤読、storeのusername+community scan混在が原因）。PPE→whitelist相関が判明し、自分の1件のみwhitelistedだった当初見立ては撤回。残ギャップは MCP系PPE 2件のみ（t_8646bcf9 running で support 経路を対応中）。

## 提案（1件）
**t_2713a67b — agentic whitelistスキャンスクリプトの恒久化**
- 根拠: reports/agentic-whitelist-2026-09.md（commit 9b11b6d/d9ba172）手順2が参照する `scripts/check_agentic_whitelist.sh` がリポジトリに実在しない（16:20実測 MISSING）。実体はワークスペース scratch の verify_v87.py のみで、タスク完了後に失われる。QA申し送り「live APIで毎回実測照合せよ」を固定実装で支える。
- 優先度: 中（自動復旧は阻害しないが、再検証コストと誤readの再発リスク）
- リスク: 低（読み取り専用APIスクリプト追加のみ）
- 成功指標: exit 0 + JSONに whitelisted>=62・total_ppe_gaps<=2
- 検証コマンド: `bash scripts/check_agentic_whitelist.sh | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['whitelisted']>=62"`
- 代替案: APIスキーマ変更でスキャン不能なら error フィールドで返し、t_8646bcf9 の support 問い合わせ手順へフォールバック。

## 却下した案
- 3 readyタスク（t_fee7c78e/t_916b2902/t_940c0adc、16:04 Hunter産）への介入 → worker/qoderの担当で供給十分。
