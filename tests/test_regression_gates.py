"""回帰ゲート — 修正済みバグの再発をpytestで機械検出（t_4e710909 / evolution v105）。

出典: arXiv 2509.25370 'Where LLM Agents Fail' (AgentErrorTaxonomy 5分類)。
教訓notepadの自由文ではなく、done済み「コードバグ」種の実失敗を
再検出コマンドとしてこのファイルに固定する。各テストのdocstringに
元の失敗タスクIDと分類(category)を明記。

ゲートは3層:
  1. 静的ゲート（repo内ファイルのみ、決定論的）
     - test_kenkaku_per_page_retry_present: v144 retry除去の回検出
     - test_loop_health_escalation_invariant_documented: v133b band再設定の回検出
     - test_done_guard_has_result_check: v151 条件(h)除去の回検出
  2. 実行ゲート（脚本をtmp stateで駆動し不変条件を実測）
     - test_loop_health_band_reset_invariant: 不変条件 last_escalate_streak<=streak
  3. 台帳ゲート（scripts/regression_gates_ledger.py の機械可読メトリクス）
     - result空 / プロトコル違反 / checkpoint打刻 / lessons条数 → 閾値0
     - SKILL.md肥大 / no_agent script解決 → レチェット（悪化のみfail、改善で自動絞込）

ネットワーク・応募ロジック・モデル設定には一切触れない。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

KENKAKU = REPO_ROOT / "kensho" / "scraping" / "sources" / "kenkaku.py"
LOOP_HEALTH = REPO_ROOT / "scripts" / "loop_health.sh"
LEDGER = REPO_ROOT / "scripts" / "regression_gates_ledger.py"


def _resolve_guard() -> Path:
    """kanban_done_guard.pyの絶対パス解決（QA run490申し送り対応）。

    cron起動時はHOME=/home/atushi/.hermes/profiles/kensho-sweeps/home
    （プロファイル内二重HOME）に切り替わるため Path.home() 単独では
    必ず解決失敗→test_done_guard_has_result_checkが環境依存FAILになる。
    HOME解決失敗時のフォールバックとして実体のある絶対パスを順に参照する。
    """
    rel = Path(".hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py")
    roots = [Path.home(), Path("/home/atushi")]
    for root in roots:
        cand = root / rel
        if cand.exists():
            return cand
    return roots[0] / rel  # 不在時は従来パスをエラーメッセージに使う


GUARD = _resolve_guard()

JST = timezone(timedelta(hours=9))


# ─── 1. 静的ゲート（決定論的、外部状態非依存） ───────────────────────────────


def test_kenkaku_per_page_retry_present() -> None:
    """[action系 v144 / t_902d09ac] kenkaku.py ページ単位timeout retryの回帰検出。

    失敗史: ken-kaku.comのレイテンシjitterでConnectTimeout→ページ毎に全放棄し
    KENKAKU取得avg 16.3→10.4件へ悪化（9/14実測CT47件/day）。v144で
    fetchのみ最大2回リトライ追加（commit 7448138）。retry定数・loop・バックオフの
    どれか1つでも消えたら再発としてfail。
    """
    src = KENKAKU.read_text(encoding="utf-8")
    assert "_KENKAKU_MAX_RETRIES" in src, "v144 retry定数が消えた（再発）"
    assert "_KENKAKU_RETRY_BACKOFF" in src, "v144 backoff定数が消えた（再発）"
    assert re.search(r"for\s+attempt\s+in\s+range\(\s*1\s*\+\s*_KENKAKU_MAX_RETRIES\s*\)", src), (
        "retryループ（1+max_attempts形式）が消えた（再発）"
    )
    assert "time.sleep(_KENKAKU_RETRY_BACKOFF)" in src, "リトライ待機が消えた（再発）"
    # retryはfetchのみ対象: パース部（2つ目のtry）へ展開されていないこと
    assert src.count("except Exception as e:") >= 2, "fetch/parseの二層try構造が崩れた"


def test_loop_health_escalation_invariant_documented() -> None:
    """[memory系 v133b / t_c34941bd] park後band未リセット不変条件の回帰検出。

    失敗史: loop_health v133のpark成功時、持続band(last_escalate_streak)が
    現streakへ再設定されず band=11 > streak=0 の不変条件破れが残留し、
    healthy boardでescalationが焼き続けた（v92回帰級の盲点）。
    v133b/修正ガードのコード痕跡（band<=streak条件）が消えたら再発。
    """
    src = LOOP_HEALTH.read_text(encoding="utf-8")
    assert re.search(r"PREV_ESCALATE_STREAK\"?\s+-gt\s+0\s+&&\s+\"?\$?PREV_ESCALATE_STREAK\"?\s+-le", src) or re.search(
        r"-le\s+\"\$STREAK_COUNT\"", src
    ), "v133b不変条件ガード (last_escalate_streak <= streak) がloop_health.shから消えた"
    assert "last_escalate_streak" in src, "state不変キーが消えた（出力スキーマ破壊）"


def test_done_guard_has_result_check() -> None:
    """[action系 v151 / t_274a3024] kanban_done_guard 条件(h) result非空検査の回帰検出。

    失敗史: native kanban_complete(summary=...) 経路が構造的にtasks.resultを
    空にし、done 16件中15件空・QA申し送り2件（9/15 sqlite実測）。
    v151でguard条件(h)+hook配線で塞いだ（commit 505be31）。guard本体は
    ~/.hermes側にあるためrepo外依存を許容し、存在しない場合はskipでなく
    引用側のledgerで検知する（このテストはguard存在時に内容検査）。
    """
    if not GUARD.exists():
        # kensho-workerの環境にguardが無い場合は「検査不能」を明示失敗させる
        # （黙って通すとv151病理の再発検知能力自体が消えるため）
        raise AssertionError(f"kanban_done_guard.py not found at {GUARD} — v151 result-column gate cannot be verified")
    src = GUARD.read_text(encoding="utf-8")
    assert "result" in src and ("条件(h)" in src or "result_column_state" in src), (
        "done_guard条件(h) tasks.result非空検査が消えた（再発）"
    )
    assert "result_column_state" in src, "条件(h)実関数が消えた"


# ─── 2. 実行ゲート（tmp state駆動で不変条件を実測） ─────────────────────────


def _run_loop_health(state: dict[str, Any], now: int) -> tuple[dict[str, Any], dict[str, Any]]:
    """loop_health.shをdry-run/no-parkで走らせ (stdout, 更新後state) を返す。"""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        state_file = Path(td) / "loop_health_state.json"
        state_file.write_text(json.dumps(state), encoding="utf-8")
        tasks = json.dumps([
            {"id": "t_gatecheck", "status": "running", "title": "healthy", "started_at": now - 3600, "result": None}
        ])
        proc = subprocess.run(
            [
                "bash",
                str(LOOP_HEALTH),
                "--tasks",
                tasks,
                "--state",
                str(state_file),
                "--dry-run",
                "--no-park",
                "--board",
                "kensho-ai-team",
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert proc.returncode == 0, f"loop_health.sh failed: {proc.stderr[:300]}"
        return json.loads(proc.stdout), json.loads(state_file.read_text(encoding="utf-8"))


def test_loop_health_band_reset_invariant() -> None:
    """v133病理の生実測: park後band(11)>streak(0)の残留stateを healthy boardで
    1回走らせ、(a)escalation=False (b)新stateのlast_escalate_streak<=streak を検証。
    """
    now = int(datetime.now(tz=JST).timestamp())
    stale = {
        "score": 41,
        "streak": 0,
        "last_escalate_streak": 11,
        "last_low_band": 11,
        "escalated_at": "",
        "park_cooldown_until": 0,
        "park_after_h": 72,
        "last_park_action": "none",
        "last_park_ts": "",
        "last_park_result": "",
        "last_park_target": "",
        "last_run_ts": datetime.now(tz=JST).isoformat(timespec="seconds"),
        "escalation_active": True,
    }
    out, new_state = _run_loop_health(stale, now)
    assert out["score"] >= 55, f"fixture board should be healthy, got score={out['score']}"
    assert out["escalation"] is False, (
        f"band=11>streak=0の古いbandでescalationが再点いた（v133b回帰）: {out['escalation']}"
    )
    assert new_state["last_escalate_streak"] <= new_state["streak"], (
        f"不変条件 last_escalate_streak({new_state['last_escalate_streak']}) <= streak({new_state['streak']}) 破れ"
    )


# ─── 3. 台帳ゲート（ledgerメトリクス: 閾値0 / レチェット） ──────────────────
# レチェット台帳: 現在の実測で「悪化のみfail」を固定する基準値。
# 引き下げ（改善）はテストが自動で提案 → 人間がこの値を直して commit。
# 引き上げ（悪化）は即fail = 該当クラスの再発。
RATCHETS: dict[str, int] = {
    "skill_md_oversize": 75,  # 9/15実測: 全profile+global SKILL.md >20KB（kensho系59/75）
    # 9/16 t_4e710909で両job修正済み → hard-zero化（dm_scan.py/apify_run_monitor.py実体配置+登録是正）
    "noagent_script_path_contract": 0,
}


def _ledger() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(LEDGER)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"ledger failed: {proc.stderr[:300]}"
    return dict(json.loads(proc.stdout))


def _gate(ledger: dict[str, Any], name: str) -> dict[str, Any]:
    assert name in ledger["gates"], f"gate '{name}' missing from ledger — regression of the gate itself"
    return dict(ledger["gates"][name])


def test_gate_result_column_empty_after_v151() -> None:
    """[action v151 / t_274a3024] 基準日(9/16 00:00 JST)以降のdoneでresult空=0件。

    done_guard条件(h)導入後の再発をkanban.db直読で検出。windowは
    max(基準日, now-48h)なので古いデータは永久failにならない。
    """
    g = _gate(_ledger(), "result_column_empty_after_v151")
    assert g["value"] == 0, f"empty-result done recurrence: {g['detail']}"


def test_gate_protocol_violation_crash() -> None:
    """[reflection v103系 / t_f5f3bc95] 直近24hに「未回収」のrc=0 silent exit=0件。

    失敗史: t_39687587 4連続・t_aeb1bb44 4連続のprotocol violation（crashed）。
    板書しない完結/中断はカードがreadyへ戻り浪費するため検知専用でhard-zero。
    v167改訂(t_f5f3bc95): crash後に同一タスクの再run前進済み・またはタスクが
    done/archived終端済みのものは「回収済み」として除外。crashが最後のrunのまま
    板書無しで放置されている未回収案件だけを数える（恒久赤で他workerのpytest -x
    自己ループを阻害する構造問題を解消、QA run524起票）。
    """
    g = _gate(_ledger(), "protocol_violation_crash_24h")
    assert g["value"] == 0, f"unrecovered silent-exit recurrence: {g['detail']}"


def test_gate_checkpoint_on_exhaustion() -> None:
    """[reflection v103 / t_7c64a27c] iteration枯渇runに[checkpoint]打刻0件=再発。

    90/90枯渇の再ディスパッチはゼロ再走になるため、マイルストーン打刻が
    枯渇コストをゼロにする（v103不変条件）。v103導入以降の枯渇runのみ対象。
    """
    g = _gate(_ledger(), "checkpoint_missing_on_iteration_exhaustion")
    assert g["value"] == 0, f"uncheck-pointed exhausted runs: {g['detail']}"


def test_gate_notepad_lessons_freshness() -> None:
    """[memory v139 / t_252ab0c2] notepad lessons箇条書き6条以上=圧縮義務の再発。

    v139病理: research-agentのlessons肥大→compression timeout→教訓消失。
    鮮度5条ルールを全profileのnotepad.db走査で機械検出。
    """
    g = _gate(_ledger(), "notepad_lessons_bloat")
    assert g["value"] == 0, f"lessons bloat recurrence: {g['detail']}"


def test_gate_skill_md_ratchet() -> None:
    """[memory v104 / t_a8ede591] SKILL.md >20KBファイル数のレチェット。

    全profile横断の肥大ファイルは一度に直せない（progressive disclosureは
    1スキル1カード）ため、v104方式=基準値固定のratchetで悪化のみfail。
    基準値=RATCHETS['skill_md_oversize']。改善したら台帳のdetail報告を見て
    人間が基準値を引き下げる。
    """
    g = _gate(_ledger(), "skill_md_oversize")
    if g["value"] < RATCHETS["skill_md_oversize"]:
        print(
            f"\n[ratchet] skill_md_oversize improved to {g['value']} — "
            f"lower RATCHETS['skill_md_oversize'] in tests/test_regression_gates.py "
            f"(current {RATCHETS['skill_md_oversize']}), was 75 repo-wide/59 kensho-profile"
        )
    assert g["value"] <= RATCHETS["skill_md_oversize"], (
        f"SKILL.md bloat regressed: {g['value']} > baseline {RATCHETS['skill_md_oversize']} — {g['detail']}"
    )


def test_gate_noagent_script_path_ratchet() -> None:
    """[system / t_07e4dc05型] no_agent job script解決不能のレチェット。

    schedulerはargv=[bash, <scripts_dir>/<rel>]で発火するため、jobのscriptが
    profileスクリプト解決不能なら毎tick 'Script not found' で黙って死う。
    9/15実測: kensho-sweeps 352914c18733 (script='scripts/dm_scan.py'二重
    ネスト) は last_error='Script not found' として生きたまま発火失敗継続中
    → 基準値=1に固定して悪化検出、qaカードは別途起票（本タスク範囲外）。
    修正されたらratchet自動0へ絞込推奨（detailにviolations一覧）。
    """
    g = _gate(_ledger(), "noagent_script_path_contract")
    if g["value"] == 0 and RATCHETS["noagent_script_path_contract"] > 0:
        print("\n[ratchet] no_agent script path fully fixed — lower RATCHETS to 0 for hard-zero gate")
    assert g["value"] <= RATCHETS["noagent_script_path_contract"], (
        f"no_agent script-path recurrence: {g['value']} > baseline "
        f"{RATCHETS['noagent_script_path_contract']} — {g['detail']}"
    )
