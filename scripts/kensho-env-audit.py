#!/usr/bin/env python3
"""
kensho-env-audit.py — 環境情報の定期棚卸し
実環境（IP/MAC/ポート/プロセス/サービス）と Hermes memory の整合性をチェックし、
「設定を忘れて一から調べ直す」問題を防ぐ。
出力は構造化JSON → cronが差異を報告。
"""

import json
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path("/home/atushi/.hermes/profiles/kensho-sweeps/memories/MEMORY.md")
USER_FILE = Path("/home/atushi/.hermes/profiles/kensho-sweeps/memories/USER.md")

# 監視対象: (名前, タイプ, 接続先)
TARGETS = [
    {
        "name": "GALLERIA(RTX3090) SSH",
        "type": "tcp",
        "host": "192.168.1.247",
        "port": 22,
        "expected": "atush@192.168.1.247",
    },
    {
        "name": "GALLERIA vLLM(トンネル経由)",
        "type": "tcp",
        "host": "127.0.0.1",
        "port": 18020,
        "expected": "qwen3.8-27b@18020",
    },
    {
        "name": "GALLERIA SSHトンネル(18021)",
        "type": "tcp",
        "host": "127.0.0.1",
        "port": 18021,
        "expected": "tunnel→18020",
    },
    {
        "name": "TencentDB Memory Gateway",
        "type": "tcp",
        "host": "127.0.0.1",
        "port": 8420,
        "expected": "memory_tencentdb",
    },
    {"name": "Ollama embedding(bge-m3)", "type": "tcp", "host": "127.0.0.1", "port": 11434, "expected": "embedding"},
    {"name": "SearXNG検索", "type": "tcp", "host": "127.0.0.1", "port": 8888, "expected": "web search"},
]


def tcp_check(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_proxy_ports() -> list:
    """SOCKS5プロキシ(1084-1089)の生存確認 — Windows側で動いているためpowershell経由"""
    results = []
    try:
        r = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | "
                "Where-Object {$_.LocalPort -in 1084,1085,1087,1089} | "
                "Select-Object -ExpandProperty LocalPort",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        listening = {int(p) for p in r.stdout.split() if p.strip().isdigit()}
    except Exception:
        listening = set()
    for port in [1084, 1085, 1087, 1089]:
        results.append({"name": f"SOCKS5 proxy :{port}", "alive": port in listening})
    return results


def check_services() -> list:
    """systemdユーザーサービスの状態"""
    results = []
    for svc in ["memory-tencentdb-gateway.service", "kensho-qwen-tunnel.service", "kensho-qwen-wake-proxy.service"]:
        try:
            r = subprocess.run(
                ["systemctl", "--user", "is-active", svc],
                capture_output=True,
                text=True,
                timeout=10,
            )
            results.append({"name": svc, "active": r.stdout.strip() == "active"})
        except Exception:
            results.append({"name": svc, "active": None})
    return results


# 既知の無視問題（解消されるまで毎回報告しない）
KNOWN_ISSUES = {
    "DOWN: SOCKS5 proxy :1084",  # zinは既知の障害（configから一時無効化中）
}


def read_memory() -> str:
    try:
        return MEMORY_FILE.read_text(encoding="utf-8")
    except Exception:
        return ""


def main():
    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "checks": [],
        "issues": [],
    }

    # TCPチェック
    for t in TARGETS:
        alive = tcp_check(t["host"], t["port"])
        report["checks"].append({"name": t["name"], "alive": alive, "expected": t["expected"]})
        if not alive:
            report["issues"].append(f"DOWN: {t['name']} ({t['host']}:{t['port']})")

    # プロキシ
    for p in check_proxy_ports():
        report["checks"].append(p)
        if not p["alive"]:
            report["issues"].append(f"DOWN: {p['name']}")

    # systemdサービス
    for s in check_services():
        report["checks"].append(s)
        if s["active"] is False:
            report["issues"].append(f"INACTIVE: {s['name']}")

    # メモリの有無
    mem = read_memory()
    report["memory_chars"] = len(mem)
    if not mem:
        report["issues"].append("MEMORY.mdが空/無い")

    # 既知問題を除外
    report["issues"] = [i for i in report["issues"] if i not in KNOWN_ISSUES]

    # 結果
    all_ok = len(report["issues"]) == 0
    report["status"] = "OK" if all_ok else "ISSUES_FOUND"
    report["summary"] = f"{len(report['checks'])}項チェック / {len(report['issues'])}件の問題"

    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
