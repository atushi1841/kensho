"""
Kensho WiFi Manager — WiFiアダプター状態確認・再接続（セーフ）
v2.1: Restart-NetAdapter採用、重複排除、utils/network使用
"""
from __future__ import annotations

import subprocess, time
from utils.process import run_pwsh
from utils.network import is_adapter_up


def ping(ip: str = '8.8.8.8', count: int = 2, timeout_sec: int = 3) -> bool:
    """軽量ping（戻り値: bool）"""
    try:
        r = subprocess.run(
            ['ping', '-n', str(count), ip, '-w', str(timeout_sec * 1000)],
            capture_output=True, timeout=timeout_sec + 2
        )
        out = r.stdout.decode('cp932', errors='replace')
        import re
        m = re.search(r'Received\s*=\s*(\d+)', out)
        if m:
            return int(m.group(1)) >= 1
        return False
    except Exception:
        return False


def reconnect_adapter(name: str) -> bool:
    """
    アダプターをセーフに再接続（Restart-NetAdapter）。
    Disable/Enableよりマイルドで、切断時間が短い。
    """
    run_pwsh(f"Restart-NetAdapter -Name '{name}' -Confirm:$false")
    time.sleep(5)  # 復旧待ち
    # 復旧確認
    if not is_adapter_up(name):
        # Restartが効かない場合のみDisable/Enable（最終手段）
        run_pwsh(f"Disable-NetAdapter -Name '{name}' -Confirm:$false")
        time.sleep(2)
        run_pwsh(f"Enable-NetAdapter -Name '{name}' -Confirm:$false")
        time.sleep(8)
    return is_adapter_up(name)
