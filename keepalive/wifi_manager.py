"""
Kensho WiFi Manager — WiFiアダプター状態確認・再接続（セーフ）
v2.2: Linux対応（WSL2ではWiFi管理不可、pingのみ対応）
"""
from __future__ import annotations

import platform
import re
import subprocess
import time
from utils.process import run_pwsh
from utils.network import is_adapter_up


def ping(ip: str = '8.8.8.8', count: int = 2, timeout_sec: int = 3) -> bool:
    """軽量ping（戻り値: bool）"""
    try:
        if platform.system() == 'Linux':
            # Linux: ping -c <count> -W <timeout_sec>
            r = subprocess.run(
                ['ping', '-c', str(count), ip, '-W', str(timeout_sec)],
                capture_output=True, timeout=timeout_sec + 2
            )
            out = r.stdout.decode('utf-8', errors='replace')
            # Linux ping: "1 packets transmitted, 1 received, ..."
            m = re.search(r'(\d+)\s+received', out)
            if m:
                return int(m.group(1)) >= 1
            return r.returncode == 0
        else:
            # Windows: ping -n <count> -w <timeout_ms>
            r = subprocess.run(
                ['ping', '-n', str(count), ip, '-w', str(timeout_sec * 1000)],
                capture_output=True, timeout=timeout_sec + 2
            )
            out = r.stdout.decode('cp932', errors='replace')
            m = re.search(r'Received\s*=\s*(\d+)', out)
            if m:
                return int(m.group(1)) >= 1
            return False
    except Exception:
        return False


def reconnect_adapter(name: str) -> bool:
    """
    アダプターをセーフに再接続。
    Linux（WSL2）: WiFi管理不可なので常にFalseを返す。
    Windows: Restart-NetAdapterを使用。
    """
    if platform.system() == 'Linux':
        # WSL2 は Windows の WiFi アダプターを直接操作できない
        return False

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
