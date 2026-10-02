#!/usr/bin/env python3
import os
import json
from datetime import datetime

def check_ai_team_status():
    status = {"timestamp": datetime.now().isoformat(), "components": {}}
    
    # Check Hermes
    hermes_status = {"status": "unknown", "checks": []}
    try:
        result = os.popen("pgrep -f hermes").read()
        if result.strip():
            hermes_status["status"] = "running"
            hermes_status["checks"].append("Hermes process detected")
        else:
            hermes_status["status"] = "stopped"
            hermes_status["checks"].append("Hermes process not detected")
    except:
        hermes_status["status"] = "error"
        hermes_status["checks"].append("Error checking Hermes")
    
    # Check config
    try:
        with open('/mnt/d/Project2/kensho/config.yaml', 'r') as f:
            config = f.read()
        if "telegram:" in config:
            hermes_status["checks"].append("Telegram configured")
        if "enabled: true" in config:
            hermes_status["checks"].append("Telegram enabled")
    except Exception as e:
        hermes_status["checks"].append(f"Config error: {e}")
    
    status["components"]["hermes"] = hermes_status
    
    # Check Kensho
    kensho_status = {"status": "unknown", "checks": []}
    kensho_files = [
        '/mnt/d/Project2/kensho/config.yaml',
        '/mnt/d/Project2/kensho/telegram_bot.py',
        '/mnt/d/Project2/kensho/action_optimizer.py'
    ]
    for file_path in kensho_files:
        if os.path.exists(file_path):
            kensho_status["checks"].append(f"{os.path.basename(file_path)} exists")
        else:
            kensho_status["checks"].append(f"{os.path.basename(file_path)} missing")
    
    session_files = [f for f in os.listdir('/mnt/d/Project2/kensho/data') if f.startswith('x_session')]
    kensho_status["checks"].append(f"{len(session_files)} session files found")
    status["components"]["kensho"] = kensho_status
    
    return status

if __name__ == "__main__":
    result = check_ai_team_status()
    print(json.dumps(result, indent=2))
