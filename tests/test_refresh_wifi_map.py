"""scripts/refresh_wifi_map.py の回帰テスト（2026-09-25 nightly-qa 追加）。

背景（実測）: cron の最小PATH (/usr/bin:/bin) では bare な `powershell.exe` が解決できず、
`_ps()` が無音で空文字を返す → ports=[] / wlan={} → 「全垢 proxy_state=停止」
「adapter_state=未検出」の偽マップを書き込む。これが applier の network_outage_reason()
を経由して稼働中の kudou(50件/日) を「圏外」と誤判定し応募スキップを招く。
本テストは (1) PowerShell の絶対パス解決 (2) 実測全滅時に既存値を保持すること を固定する。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.refresh_wifi_map as m


def test_powershell_prefers_existing_absolute_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    """候補の絶対パスが存在すればそれを返す（PATH依存を排除）。"""
    first = m.PS_CANDIDATES[0]
    monkeypatch.setattr(m.os.path, "exists", lambda p: p == first)
    assert m._powershell() == first


def test_powershell_falls_back_when_no_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    """候補が無ければ shutil.which → それも無ければ bare 名にフォールバックする。"""
    monkeypatch.setattr(m.os.path, "exists", lambda p: False)
    monkeypatch.setattr(m.shutil, "which", lambda name: None)
    assert m._powershell() == m.PS_FALLBACK


def test_failed_measurement_preserves_existing_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """実測が全滅した場合、proxy_state/adapter_state/egress_ip を偽値で上書きしない。"""
    map_path = tmp_path / "account_wifi_map.json"
    original = {
        "accounts": [
            {
                "key": "kudou",
                "port": 1082,
                "adapter": "kudou_RM10JE_B",
                "transport": "POVOスマホHS",
                "adapter_state": "接続",
                "proxy_state": "listen",
                "egress_ip": "106.146.21.233",
                "egress_ok": True,
            }
        ]
    }
    map_path.write_text(json.dumps(original, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(m, "MAP", map_path)
    # 実測系を全滅させる（cron最小PATHで起きる状況の再現）
    monkeypatch.setattr(m, "collect_ips", lambda: {})
    monkeypatch.setattr(m, "collect_wlan", lambda: {})
    monkeypatch.setattr(m, "collect_ports", lambda: set())
    monkeypatch.setattr(m, "_curl_ip", lambda *a, **k: "")

    assert m.main() == 0

    after = json.loads(map_path.read_text(encoding="utf-8"))
    ent = after["accounts"][0]
    assert ent["adapter_state"] == "接続"
    assert ent["proxy_state"] == "listen"
    assert ent["egress_ip"] == "106.146.21.233"
    assert after["measurement_ok"] is False


def test_successful_measurement_writes_measured_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """実測成功時は測定値で更新される（保持ガードが更新を妨げない）。"""
    map_path = tmp_path / "account_wifi_map.json"
    map_path.write_text(
        json.dumps({"accounts": [{"key": "kudou", "port": 1082, "adapter": "kudou_RM10JE_B",
                                 "transport": "POVOスマホHS", "adapter_state": "未検出",
                                 "proxy_state": "停止", "egress_ip": "", "egress_ok": False}]},
                   ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(m, "MAP", map_path)
    monkeypatch.setattr(m, "collect_ips", lambda: {"kudou_RM10JE_B": "10.32.223.239"})
    monkeypatch.setattr(m, "collect_wlan",
                        lambda: {"kudou_RM10JE_B": {"state": "接続", "ssid": "RM10JE_B", "signal": "80%"}})
    monkeypatch.setattr(m, "collect_ports", lambda: {1082})
    monkeypatch.setattr(m, "egress_ip", lambda port: "106.146.21.233")
    monkeypatch.setattr(m, "_curl_ip", lambda *a, **k: "219.104.132.236")

    assert m.main() == 0

    after = json.loads(map_path.read_text(encoding="utf-8"))
    ent = after["accounts"][0]
    assert after["measurement_ok"] is True
    assert ent["adapter_state"] == "接続"
    assert ent["proxy_state"] == "listen"
    assert ent["egress_ip"] == "106.146.21.233"
    assert ent["egress_ok"] is True
    assert ent["egress_warn_home"] is False


def test_broken_static_contract_aborts_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """静的対応(adapter/port)が欠落した破損mapは上書きせず、exit 2で中止する。

    背景（2026-09-25 QA実測）: live項目だけの最小JSONで data/account_wifi_map.json を
    上書きすると adapter が引けず proxy_state="停止"（実際はLISTEN）が毎tick書き込まれ、
    稼働垢 kudou(50件/日) が network_outage_reason で「圏外」になり応募停止した。
    破損マップは触らないことを固定する。
    """
    map_path = tmp_path / "account_wifi_map.json"
    broken = {
        "accounts": [
            {"key": "kudou", "display": "@kudou_aoshi", "adapter_state": "未検出",
             "proxy_state": "停止", "egress_ip": "", "egress_ok": False}
        ],
        "home_ip": "219.104.132.236",
        "measurement_ok": True,
    }
    raw = json.dumps(broken, ensure_ascii=False) + "\n"
    map_path.write_text(raw, encoding="utf-8")
    monkeypatch.setattr(m, "MAP", map_path)
    monkeypatch.setattr(m, "collect_ips", lambda: {"kudou_RM10JE_B": "10.32.223.239"})
    monkeypatch.setattr(m, "collect_wlan",
                        lambda: {"kudou_RM10JE_B": {"state": "接続", "ssid": "RM10JE_B"}})
    monkeypatch.setattr(m, "collect_ports", lambda: {1082})
    monkeypatch.setattr(m, "_curl_ip", lambda *a, **k: "219.104.132.236")

    assert m.main() == 2
    assert map_path.read_text(encoding="utf-8") == raw  # 破損mapを書き換えていない
    assert "adapter/port" in capsys.readouterr().out
