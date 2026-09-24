"""Tests for scripts/audit_bot_safety.py 検査6「日跨ぎ規則性」(critic v143 / t_32c2723a).

_regularity_signals はモジュールAUDIT_PATHを読むため、tmp_path に合成 audit.jsonl を
書き、パッチして検証する（ネットワーク・実データ依存なし）。
"""

import importlib.util
import json
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


def _day_rows(acct: str, back: int, start_min: int, n: int) -> list[dict]:
    """DATEからback日前に初動start_min(分)、n件のsuccess行を生成."""
    d0 = (END - timedelta(days=back)).replace(tzinfo=JST)
    base = d0.replace(hour=start_min // 60, minute=start_min % 60, second=0, microsecond=0)
    out = []
    for i in range(n):
        ts = (base + timedelta(minutes=3 * i)).astimezone(UTC).isoformat().replace("+00:00", "Z")
        out.append({"timestamp": ts, "account": acct, "action_type": "retweet", "target": "12345", "status": "success"})
    return out


def _acct_rows(acct: str, starts: list[int], counts: list[int]) -> list[dict]:
    lines: list[dict] = []
    for back, (s, c) in enumerate(zip(starts, counts)):
        lines.extend(_day_rows(acct, back, s, c))
    return lines


def test_low_start_stdev_flagged(tmp_path, monkeypatch):
    """初動stdev<2.5分 → 件数CVが閾値超でも OR 条件で検出（atushi16/zin実測相当）."""
    # stdev~1.4分(<2.5), counts 70-130でCV>0.01
    lines = _acct_rows(
        "atushi16",
        [500, 500, 500, 500, 500, 500, 500],  # 初動時刻は全て同じ500（1時間20分）
        [70, 100, 130, 90, 120, 80, 110],
    )
    monkeypatch.setattr(mod, "AUDIT_PATH", _write_audit(tmp_path, lines))
    sigs = mod._regularity_signals(DATE)
    # 修正後の閾値ではstdev<2.5で検出すべき
    assert len(sigs) == 1
    assert "[正規性]" in sigs[0] and "atushi16" in sigs[0]
    assert "初動stdev" in sigs[0]
    assert "2.5" in sigs[0]  # 新しい閾値を検証


def test_low_count_cv_flagged(tmp_path, monkeypatch):
    """件数CV<0.01 → 初動stdevが大きくても OR 条件で検出."""
    # stdev~69分, CV=0.00(<0.01) - CVのみの閾値未満
    lines = _acct_rows("kudou", [500, 700, 550, 650, 520, 680, 540], [100] * 7)  # stdev~69分, CV=0
    monkeypatch.setattr(mod, "AUDIT_PATH", _write_audit(tmp_path, lines))
    sigs = mod._regularity_signals(DATE)
    assert len(sigs) == 1 and "件数CV" in sigs[0]
    assert "0.01" in sigs[0]  # 新しい閾値を検証


def test_no_signal_when_random(tmp_path, monkeypatch):
    """初動stdev>=2.5分かつCV>=0.01 → シグナルなし（偽陽性ガード）."""
    # stdev~87分(>=2.5), CV~0.08(>=0.01) - どちらの閾値も超える
    lines = _acct_rows(
        "zin20120731",
        [480, 600, 520, 660, 540, 620, 500],  # 初動時刻が大きく変動
        [60, 100, 80, 120, 70, 110, 90],    # 日次件数に大きな変動
    )
    monkeypatch.setattr(mod, "AUDIT_PATH", _write_audit(tmp_path, lines))
    assert mod._regularity_signals(DATE) == []


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
    lines = _acct_rows("atushi16", [500, 502, 498, 501, 499, 503, 497], [40, 38, 42, 41, 39, 40, 41])
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
