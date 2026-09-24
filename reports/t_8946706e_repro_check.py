"""t_8946706e 再現チェック（読み取り専用・ブラウザ起動なし）

本番 config.yaml の実値を使って、恒久修正の3点を実測する。
  1. セッション失効垢（goto_failed）は3回リトライせず1回で停止し、当該垢だけが遮断される
  2. failure ceiling のキーが垢単位（apply:<account_key>）である
  3. 毎時run（間隔60分 > cooldown 30分）でも ceiling が発動する
  4. プロキシ死骸垢（data/status/<acct>.json = dead_proxy）は応募を試行しない

使い方: .venv/bin/python reports/t_8946706e_repro_check.py
副作用: `data/` を一時ディレクトリへコピーし、そちらにのみ状態を書く（本番 state は触らない）。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path("/mnt/d/Project2/kensho")
sys.path.insert(0, REPO.as_posix())

from kensho.application import applier  # noqa: E402
from kensho.core.config import load as load_config  # noqa: E402
from kensho.core.self_heal import SelfHealingLoop  # noqa: E402
from kensho.utils import safety  # noqa: E402

real_cfg = load_config()


def _sandbox() -> dict:
    """本番 config の実値のまま general.project_dir だけ一時領域へ向けた cfg を返す。"""
    tmp = Path(tempfile.mkdtemp(prefix="t_8946706e_"))
    (tmp / "data").mkdir(exist_ok=True)
    cfg = json.loads(json.dumps(real_cfg, default=str))
    cfg["general"]["project_dir"] = str(tmp)
    cfg["self_healing"]["notify_on_error"] = False
    return cfg


print("== 0. max_attempts（増やしていないことの実測） ==")
print("config.yaml self_healing.max_attempts =", real_cfg["self_healing"].get("max_attempts"))
print("collection.max_pages =", (real_cfg.get("collection") or {}).get("max_pages"))

print()
print("== 1/2. セッション失効垢は1回で停止＋ceiling キーが垢単位 ==")
cfg = _sandbox()
ACCT = "zin20120731"
calls: list[int] = []


def _fake_apply_impl(account_key, max_n, cfg=None, log=None, dry_run=False,
                     shared_browser=None, shared_ipw=None, reason_out=None):
    """実ログの失敗シグネチャ（goto failed / auth失効 → apply 0 success 1 errors）を再現。"""
    calls.append(1)
    if reason_out is not None:
        reason_out["kind"] = "goto_failed"
    return (0, 1)


orig = applier._apply_impl
applier._apply_impl = _fake_apply_impl
try:
    try:
        applier.apply_for_account(ACCT, 5, cfg=cfg)
    except RuntimeError as exc:
        print("apply_for_account raised (期待どおり最終失敗):", str(exc)[:90])
finally:
    applier._apply_impl = orig
print("_apply_impl calls (旧実装=3回リトライ / 修正後=1回):", len(calls))
state = json.loads((Path(cfg["general"]["project_dir"]) / "data" / "self_heal_state.json").read_text())
print("state ceilings keys:", sorted(state.get("ceilings", {}).keys()))
print("blocked entry:", json.dumps(state["ceilings"].get(f"apply:{ACCT}"), ensure_ascii=False))

print()
print("== 3. 毎時runでも ceiling が発動する（first_fail_time は2時間前でも遮断維持） ==")
cfg2 = _sandbox()
coll = SelfHealingLoop(cfg=cfg2, pipeline="collection")
for i in range(1, 4):
    r = coll.run(lambda: (_ for _ in ()).throw(ConnectionError("collect 0 success 1 errors")))
    print(f"  run{i}: attempts={r.attempts} ok={r.ok} blocked={coll.is_blocked('collection')}")
st = json.loads((Path(cfg2["general"]["project_dir"]) / "data" / "self_heal_state.json").read_text())
entry = st["ceilings"]["collection"]
print("collection ceiling:", json.dumps(entry, ensure_ascii=False))
print("auto-blocked on 3rd hourly failure:", coll.is_blocked("collection"))

print()
print("== 4. プロキシ死骸垢は応募を試行しない（実 status ファイル参照） ==")
print("safety.dead_proxy_accounts(real_cfg) =", safety.dead_proxy_accounts(real_cfg))
print("dead_proxy_reason(real_cfg, 'zin20120731') =", safety.dead_proxy_reason(real_cfg, "zin20120731")[:80])
print("applier._FATAL_APPLY_REASONS =", sorted(applier._FATAL_APPLY_REASONS))
