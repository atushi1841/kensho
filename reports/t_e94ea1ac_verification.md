# t_e94ea1ac 検証レポート — skill_md_ratchet プロジェクト分離

タスク: t_e94ea1ac (pytest恒久赤: test_gate_skill_md_ratchet SKILL.md>20KB 79>75)
対応: Plan A（推奨）— `_skill_candidates()` を kensho-* profile群 + repo skills に限定し、
RATCHETS['skill_md_oversize'] を実測値 59 へ再設定（commit 7edd9fb）。

## 検証エビデンス

$ cd /mnt/d/Project2/kensho && python3 scripts/regression_gates_ledger.py --md-table
→ | skill_md_oversize | memory | t_a8ede591 (evolution v104) | 59<=0 FAIL | SKILL.md > 20KB: 59 files, e.g. ['.hermes/profiles/kensho-critic/skills/social-media/x-bot-detection/SKILL.md', ...] |

$ python3 -m pytest tests/test_regression_gates.py::test_gate_skill_md_ratchet -q --no-header -p no:cacheprovider
→ ============================== 1 passed in 9.96s ===============================

$ git log --oneline -1
→ 7edd9fb t_e94ea1ac: skill_md_ratchet プロジェクト分離 — _skill_candidates()をkensho-*+repoに限定しRATCHETSを59へ

### 内訳（find 実測: >20KB の SKILL.md）
- kensho-* のみ = 59（kensho-sweeps=21 / kensho-revenue-worker=8 / kensho-worker=8 / kensho-critic=8 / kensho-qa=7 / kensho-revenue-qa=7 / repo skills=0）
- スコープ外・ゲート対象外: hazard-mcp=4, line-stamp=6, tai=4, default global ~/.hermes/skills=6（他プロジェクト/管轄外）
- 変更前 repo-wide=79（=59 + 20 スコープ外）→ 変更後は 59 を全数監視対象として ratchet 適用

### 残ゲート（本カードと無関係・スコープ外）
- test_gate_protocol_violation_crash は t_9f37e5e3（apply成功率測定, priority 1）の未回収 rc=0 crash が原因で赤。
  本タスク t_e94ea1ac のクラッシュは再run済みで recovered（31 raw / 30 recovered）。
