"""Tests for scripts/audit_bot_safety.py 検査6「日跨ぎ規則性」(critic v143 / t_32c2723a)。

閾値は t_3f48a43e で再校正（設計エンベロープ = cron */15 グリッド + stagger 0〜9分）:
  発火 = (1) 同一分(HH:MM)が4日以上  (2) 日次件数CV<0.01
  初動stdevは診断値であり発火条件ではない（stdev<2.5 は設計上到達可能なため）。

_regularity_signals はモジュールAUDIT_PATHを読むため、tmp_path に合成 audit.jsonl を
書き、パッチして検証する（ネットワーク・実データ依存なし）。
"""

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("audit_bot_safety", REPO / "scripts" / "audit_bot_safety.py")
mod = importlib.util.module_from_spec(_SPEC)  # type: ignore[arg-type]
_SPEC.loader.exec_module(mod)  # type: ignore[union-attr]

JST = timezone(timedelta(hours=9))
DATE = "2026-09-12"
END = datetime.fromisoformat(DATE)


def _write_audit(tmp_path: Path, lines: list[dict]) -> Path:
    p = tmp_path / "audit.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for r in lines:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return p


def _day_rows(acct: str, back: int, start_min: int, n: int, end: datetime | None = None) -> list[dict]:
    """DATEからback日前に初動start_min(分)、n件のsuccess行を生成."""
    d0 = ((end or END) - timedelta(days=back)).replace(tzinfo=JST)
    base = d0.replace(hour=start_min // 60, minute=start_min % 60, second=0, microsecond=0)
    out = []
    for i in range(n):
        ts = (base + timedelta(minutes=3 * i)).astimezone(UTC).isoformat().replace("+00:00", "Z")
        out.append({"timestamp": ts, "account": acct, "action_type": "retweet", "target": "12345", "status": "success"})
    return out


def _acct_rows(acct: str, starts: list[int], counts: list[int], end: datetime | None = None) -> list[dict]:
    lines: list[dict] = []
    for back, (s, c) in enumerate(zip(starts, counts)):
        lines.extend(_day_rows(acct, back, s, c, end))
    return lines


# ---- detection power: 機械的正確さを注入したfixtureでは必ず発火 --------------------


def test_identical_minute_7days_flagged(tmp_path, monkeypatch):
    """初動が7日間すべて同一分（HH:MM完全一致）→ 発火（反復7日 / 閾値4日以上）."""
    lines = _acct_rows("atushi16", [500] * 7, [100, 101, 100, 100, 101, 100, 101])
    monkeypatch.setattr(mod, "AUDIT_PATH", _write_audit(tmp_path, lines))
    sigs = mod._regularity_signals(DATE)
    assert len(sigs) == 1
    assert "[正規性]" in sigs[0] and "atushi16" in sigs[0]
    assert "7日中7日一致" in sigs[0]


def test_identical_minute_4days_flagged(tmp_path, monkeypatch):
    """同一分が7日中4日（=閾値ちょうど）→ 発火。件数は変動させCVを条件から外す."""
    lines = _acct_rows("kudou", [500, 500, 500, 500, 620, 700, 560], [100, 130, 90, 120, 95, 140, 105])
    monkeypatch.setattr(mod, "AUDIT_PATH", _write_audit(tmp_path, lines))
    sigs = mod._regularity_signals(DATE)
    assert len(sigs) == 1
    assert "7日中4日一致" in sigs[0]


def test_count_cv_fixed_flagged(tmp_path, monkeypatch):
    """日次件数CV=0.000（量が完全固定）→ 初動がばらついていても発火."""
    lines = _acct_rows("kudou", [500, 700, 550, 650, 520, 680, 540], [100] * 7)
    monkeypatch.setattr(mod, "AUDIT_PATH", _write_audit(tmp_path, lines))
    sigs = mod._regularity_signals(DATE)
    assert len(sigs) == 1 and "件数CV" in sigs[0]
    assert str(mod.REGULARITY_COUNT_CV) in sigs[0]


# ---- false positive ガード: 設計エンベロープ内では発火しない ----------------------


def test_real_observed_pattern_not_flagged(tmp_path, monkeypatch):
    """実測パターン（atushi16 2026-09-18〜24: 初動08:04〜08:22 / 件数73〜128）は発火しない."""
    lines = _acct_rows(
        "atushi16",
        [488, 491, 502, 491, 484, 487, 485],
        [106, 108, 108, 112, 106, 128, 73],
    )
    monkeypatch.setattr(mod, "AUDIT_PATH", _write_audit(tmp_path, lines))
    assert mod._regularity_signals(DATE) == []


def test_low_stdev_alone_not_flagged(tmp_path, monkeypatch):
    """初動stdev<2.5分でも反復4日未満・CV>=0.01 なら発火しない（stdevは診断値）.

    設計上 stagger 0〜9分の枠内に収まるのが正常であり、stdevの小ささだけでは
    機械的パターンと判定できない（単一枠モデルでは7日窓の41%がstdev<2.5に入る）。
    """
    lines = _acct_rows("atushi16", [500, 501, 502, 500, 501, 502, 501], [100, 120, 90, 110, 105, 95, 130])
    monkeypatch.setattr(mod, "AUDIT_PATH", _write_audit(tmp_path, lines))
    assert mod._regularity_signals(DATE) == []


def test_repeat_3days_not_flagged(tmp_path, monkeypatch):
    """同一分3日（閾値4日未満）かつ件数変動あり → 発火しない."""
    lines = _acct_rows("TankanNotes", [500, 500, 500, 530, 560, 590, 620], [100, 130, 90, 120, 95, 140, 105])
    monkeypatch.setattr(mod, "AUDIT_PATH", _write_audit(tmp_path, lines))
    assert mod._regularity_signals(DATE) == []


# ---- 境界・異常系 ---------------------------------------------------------------


def test_insufficient_days_not_judged(tmp_path, monkeypatch):
    """窓内データが3日未満（新垢等）は判定しない."""
    lines = _acct_rows("toushiwatch", [500, 505], [50, 50])
    monkeypatch.setattr(mod, "AUDIT_PATH", _write_audit(tmp_path, lines))
    assert mod._regularity_signals(DATE) == []


def test_window_is_7_days_only(tmp_path, monkeypatch):
    """8日前の行は窓外 → 窓内2日だけなら不十分扱いでシグナルなし."""
    lines = _acct_rows("atushi16", [500, 505], [30, 30])
    d8 = (END - timedelta(days=8)).replace(hour=8, minute=30, tzinfo=JST)
    lines.append({
        "timestamp": d8.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "account": "atushi16",
        "action_type": "retweet",
        "target": "1",
        "status": "success",
    })
    monkeypatch.setattr(mod, "AUDIT_PATH", _write_audit(tmp_path, lines))
    assert mod._regularity_signals(DATE) == []


def test_malformed_lines_ignored(tmp_path, monkeypatch):
    """不正JSON・不正timestamp・対象外垢は例外なく無視、正規垢は検出維持."""
    lines = _acct_rows("atushi16", [500] * 7, [100, 101, 100, 100, 101, 100, 101])
    p = _write_audit(tmp_path, lines)
    with p.open("a", encoding="utf-8") as f:
        f.write("{not json\n")
        f.write(json.dumps({"timestamp": "bad", "account": "atushi16"}) + "\n")
        f.write(
            json.dumps({
                "timestamp": "2026-09-11T01:00:00Z",
                "account": "royalkensho",
                "action_type": "retweet",
                "target": "1",
                "status": "success",
            })
            + "\n"
        )
    monkeypatch.setattr(mod, "AUDIT_PATH", p)
    sigs = mod._regularity_signals(DATE)
    assert len(sigs) == 1 and "atushi16" in sigs[0]


def test_missing_audit_file_no_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "AUDIT_PATH", tmp_path / "nope.jsonl")
    assert mod._regularity_signals(DATE) == []


def test_bad_date_no_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "AUDIT_PATH", _write_audit(tmp_path, []))
    assert mod._regularity_signals("not-a-date") == []


# ---- 既報抑制（--state）の安定キー: 鳴り続け防止 --------------------------------


def test_dedupe_key_ignores_volatile_diagnostics():
    """件数mean/CV/stdev/一致日数が動いても同一パターンのキーは不変."""
    a = (
        "[正規性] 2026-09-24 kudou 件数CV0.003(<0.01) - 日次件数がほぼ完全固定"
        " (診断: 初動stdev9.9分・件数mean131 → batch時刻ジッタ改修は別カードでGO提案)"
    )
    b = (
        "[正規性] 2026-09-24 kudou 件数CV0.004(<0.01) - 日次件数がほぼ完全固定"
        " (診断: 初動stdev8.7分・件数mean132 → batch時刻ジッタ改修は別カードでGO提案)"
    )
    assert mod._dedupe_key(a) == mod._dedupe_key(b)

    r1 = (
        "[正規性] 2026-09-24 kudou 初動08:25が7日中4日一致（stagger 0〜9分では設計上起こらない機械的パターン）"
        " (診断: 初動stdev9.9分・件数mean131 → batch時刻ジッタ改修は別カードでGO提案)"
    )
    r2 = r1.replace("4日一致", "5日一致").replace("mean131", "mean132")
    assert mod._dedupe_key(r1) == mod._dedupe_key(r2)


def test_dedupe_key_keeps_other_checks_verbatim():
    """検査1〜5の行は同一性が明確なため原文キー."""
    line = "[深夜] 2026-09-23 atushi16 retweet 3回 (深夜ガード未効? no_action_window 確認)"
    assert mod._dedupe_key(line) == line


def test_state_suppresses_same_pattern_across_mean_drift(tmp_path, monkeypatch):
    """--state: 件数meanが動いても同一パターンは2回目以降 exit 0（毎時再通知しない）.

    state保持は3日（STATE_KEEP_DAYS）のため、対象日は「今日」で検証する。
    """
    today = datetime.now(JST).date()
    target = today.isoformat()
    end_dt = datetime.fromisoformat(target)
    monkeypatch.setattr(mod, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(mod, "AUDIT_PATH", _write_audit(tmp_path, _acct_rows("atushi16", [500] * 7, [100] * 7, end_dt)))
    monkeypatch.setattr(sys, "argv", ["audit_bot_safety.py", target, "--state"])
    assert mod.main() == 1  # 1回目: 検出（exit 1 = 検出専用）
    # 同一パターンのまま件数（mean）だけ動かす
    monkeypatch.setattr(mod, "AUDIT_PATH", _write_audit(tmp_path, _acct_rows("atushi16", [500] * 7, [101] * 7, end_dt)))
    assert mod.main() == 0  # 2回目: 既報抑制で exit 0


# ── t_33113bb7 (B): MAX_ACTIONS_PER_HOUR の config 参照化 ──


def _write_cfg(tmp_path: Path, max_per_hour: int) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(f"rate_limits:\n  max_actions_per_hour: {max_per_hour}\n", encoding="utf-8")
    return p


def test_max_actions_per_hour_reads_config(tmp_path, monkeypatch):
    """config rate_limits.max_actions_per_hour=15 を読んだら、16件の過集中を検出する（旧25では検出できず）."""
    today = datetime.now(JST).date()
    target = today.isoformat()
    end_dt = datetime.fromisoformat(target)
    monkeypatch.setattr(mod, "CONFIG_PATH", _write_cfg(tmp_path, 15))
    # 16件 success の同一時間帯（1秒間隔で同一時刻帯に収める→16 > 15 → 検出。旧25では検出できず＝乖離の実証）
    base = end_dt.replace(hour=8, minute=20, second=0, microsecond=0, tzinfo=JST)
    lines = []
    for i in range(16):
        ts = (base + timedelta(seconds=i)).astimezone(UTC).isoformat().replace("+00:00", "Z")
        lines.append({"timestamp": ts, "account": "kudou", "action_type": "retweet", "target": "12345", "status": "success"})
    monkeypatch.setattr(mod, "AUDIT_PATH", _write_audit(tmp_path, lines))
    monkeypatch.setattr(sys, "argv", ["audit_bot_safety.py", target])
    assert mod.main() == 1  # 検出


def test_max_actions_per_hour_falls_back_when_config_missing(tmp_path, monkeypatch):
    """config 読込失敗時はフォールバック25（旧挙動の維持）."""
    today = datetime.now(JST).date()
    target = today.isoformat()
    end_dt = datetime.fromisoformat(target)
    # 存在しないパスを設定（フォールバック25を確認）
    monkeypatch.setattr(mod, "CONFIG_PATH", tmp_path / "nope.yaml")
    # 26件（26 > 25 フォールバック → 検出）
    base = end_dt.replace(hour=8, minute=20, second=0, microsecond=0, tzinfo=JST)
    lines = []
    for i in range(26):
        ts = (base + timedelta(seconds=i)).astimezone(UTC).isoformat().replace("+00:00", "Z")
        lines.append({"timestamp": ts, "account": "kudou", "action_type": "retweet", "target": "12345", "status": "success"})
    monkeypatch.setattr(mod, "AUDIT_PATH", _write_audit(tmp_path, lines))
    monkeypatch.setattr(sys, "argv", ["audit_bot_safety.py", target])
    assert mod.main() == 1


def test_max_actions_per_hour_no_false_positive_under_limit(tmp_path, monkeypatch):
    """閾値15で15件までは検出しない（境界）."""
    today = datetime.now(JST).date()
    target = today.isoformat()
    end_dt = datetime.fromisoformat(target)
    monkeypatch.setattr(mod, "CONFIG_PATH", _write_cfg(tmp_path, 15))
    lines = _acct_rows("kudou", [500] * 1, [15], end_dt)
    monkeypatch.setattr(mod, "AUDIT_PATH", _write_audit(tmp_path, lines))
    monkeypatch.setattr(sys, "argv", ["audit_bot_safety.py", target])
    assert mod.main() == 0
