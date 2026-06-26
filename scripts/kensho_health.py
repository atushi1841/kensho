#!/usr/bin/env python3
"""
Kensho Health Check — システム健全性をワンコマンドで確認
使い方: python scripts/kensho_health.py
"""
from __future__ import annotations

import sys, json, time, subprocess
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent
DATA = BASE / 'data'
LOGS = BASE / 'logs'
COLLECTED = DATA / 'collected.json'
DAILY_COUNTS = DATA / 'daily_counts.json'
PROCESSED = DATA / 'processed.json'

OK = '✅'
WARN = '⚠️'
ERR = '❌'
INFO = 'ℹ️'


def _check_daemon() -> tuple[str, str]:
    """daemon.py が実行中か確認"""
    try:
        r = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV', '/NH'],
            capture_output=True, timeout=10
        )
        out = r.stdout.decode('cp932', errors='replace')
        python_pids = []
        for line in out.strip().split('\n'):
            parts = line.strip('"').split('","')
            if len(parts) >= 2:
                try:
                    python_pids.append(int(parts[1]))
                except ValueError:
                    pass

        # Kenshoデーモンは複数のpython.exeプロセスとして稼働
        if not python_pids:
            return (ERR, "Pythonプロセスが起動していません")

        if len(python_pids) >= 2:
            return (OK, f"Pythonプロセス {len(python_pids)}個稼働中")
        return (INFO, f"Pythonプロセス稼働中 ({len(python_pids)}個)")

    except Exception as e:
        return (ERR, f"daemon確認失敗: {e}")


def _check_sessions() -> str:
    """セッションファイルの有効性チェック"""
    session_files = list(DATA.glob('x_session*.json'))
    if not session_files:
        return f"{ERR} セッションファイルなし"

    lines: list[str] = []
    for sf in session_files:
        age = time.time() - sf.stat().st_mtime
        days = age / 86400
        try:
            with open(sf) as f:
                data = json.load(f)
            cookies = data.get('cookies', [])
            has_auth = any(c.get('name') == 'auth_token' for c in cookies)
            has_ct0 = any(c.get('name') == 'ct0' for c in cookies)
            if has_auth and has_ct0:
                tag = OK
            else:
                tag = WARN
            lines.append(f"  {tag} {sf.name}: {days:.0f}日前 (auth={'✓' if has_auth else '✗'} ct0={'✓' if has_ct0 else '✗'})")
        except (json.JSONDecodeError, KeyError):
            lines.append(f"  {ERR} {sf.name}: 破損または形式不正")
    return '\n'.join(lines)


def _check_collected() -> str:
    """collected.json の状態チェック"""
    if not COLLECTED.exists():
        return f"{ERR} collected.json が見つかりません"

    try:
        with open(COLLECTED) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return f"{ERR} collected.json 読み込み失敗: {e}"

    items = data.get('collected', [])
    if not items:
        return f"{WARN} collected.json が空です（収集を実行してください）"

    total = len(items)
    timestamp = data.get('timestamp', '不明')
    elapsed = data.get('elapsed_seconds', 0)

    # 応募状態の集計
    all_applied = 0
    account_stats: dict[str, int] = {}
    for item in items:
        applied = item.get('applied', {})
        for acct, val in applied.items():
            if val is not None:
                all_applied += 1
                account_stats[acct] = account_stats.get(acct, 0) + 1

    has_deadline = sum(1 for i in items if i.get('deadline'))
    expired = sum(1 for i in items if i.get('days_remaining') == '期限切れ')

    total_possible = total * len(account_stats) if total > 0 and account_stats else 1
    lines = [
        f"  {INFO} 総アイテム数: {total}件",
        f"  {INFO} 最終収集: {timestamp}（{elapsed}秒）",
        f"  {INFO} 応募済み: {all_applied}/{total_possible}",
        f"  {INFO} 締切情報あり: {has_deadline}件",
        f"  {'⚠️' if expired > 0 else OK} 期限切れ: {expired}件",
    ]
    if account_stats:
        acct_line = "  " + " / ".join(f"{k}: {v}件" for k, v in sorted(account_stats.items()))
        lines.append(acct_line)
    return '\n'.join(lines)


def _check_daily_counts() -> str:
    """日次カウンターの状態"""
    if not DAILY_COUNTS.exists():
        return f"{INFO} daily_counts.json なし（本日未アクション）"

    try:
        with open(DAILY_COUNTS) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return f"{ERR} daily_counts.json 読み込み失敗"

    date = data.get('date', '?')
    counts = data.get('counts', {})
    today = datetime.now().strftime('%Y-%m-%d')

    if date != today:
        return f"{INFO} 最終記録: {date}（本日未アクション）"

    lines = [f"  {OK} 本日 ({date}) のアクション:"]
    for acct, ac in sorted(counts.items()):
        parts = [f"{k}={v}" for k, v in sorted(ac.items()) if v > 0]
        if parts:
            lines.append(f"    {acct}: {' / '.join(parts)}")
        else:
            lines.append(f"    {acct}: アクションなし")
    return '\n'.join(lines)


def _check_disk() -> str:
    """ディスク使用量チェック"""
    log_size = sum(f.stat().st_size for f in LOGS.rglob('*') if f.is_file()) if LOGS.exists() else 0
    data_size = sum(f.stat().st_size for f in DATA.rglob('*') if f.is_file()) if DATA.exists() else 0
    return (
        f"  {INFO} ログ: {log_size / 1024 / 1024:.1f}MB "
        f"（{len(list(LOGS.rglob('*')))}ファイル）\n"
        f"  {INFO} データ: {data_size / 1024:.1f}KB"
    )


def _check_config_paths() -> str:
    """config.yaml のパスが有効か簡易チェック"""
    import yaml
    config_path = BASE / 'config.yaml'
    if not config_path.exists():
        return f"{ERR} config.yaml が見つかりません"
    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        return f"{ERR} config.yaml 読み込み失敗: {e}"

    lines: list[str] = []
    for acct in cfg.get('accounts', []):
        key = acct.get('key', '?')
        sess_rel = acct.get('session', '')
        sess_path = BASE / sess_rel
        iface = acct.get('network_interface', '未設定')
        batchn = len(acct.get('schedule', {}).get('batches', []))

        if not sess_path.exists():
            lines.append(f"  {ERR} {key}: セッションファイルなし ({sess_rel})")
        else:
            lines.append(f"  {OK} {key}: {batchn}バッチ, IF={iface}")

    return '\n'.join(lines)


def _check_forcebindip() -> str:
    """ForceBindIP の存在確認"""
    bindip64 = BASE / 'tools' / 'ForceBindIP' / 'ForceBindIP64.exe'
    if bindip64.exists():
        return f"{OK} ForceBindIP64.exe あり"
    bindip = BASE / 'tools' / 'ForceBindIP' / 'ForceBindIP.exe'
    if bindip.exists():
        return f"{OK} ForceBindIP.exe あり（32bit版）"
    return f"{ERR} ForceBindIP が見つかりません（tools/ForceBindIP/ を確認）"


def _check_playwright() -> str:
    """Playwright Firefox がインストール済みか確認"""
    try:
        r = subprocess.run(
            [sys.executable, '-m', 'playwright', 'install', '--dry-run', 'firefox'],
            capture_output=True, timeout=15
        )
        out = r.stdout.decode('utf-8', errors='replace')
        if 'already' in out.lower() or not out.strip():
            return f"{OK} Playwright Firefox インストール済み"
        return f"{INFO} Playwright Firefox 要確認（`playwright install firefox`）"
    except Exception as e:
        return f"{INFO} Playwright確認スキップ: {e}"


def main() -> None:
    print("=" * 60)
    print("  Kensho 健全性チェック")
    print(f"  実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  プロジェクト: {BASE}")
    print("=" * 60)

    # 1. デーモン状態
    print("\n📡 デーモン状態")
    icon, msg = _check_daemon()
    print(f"  {icon} {msg}")

    # 2. セッションファイル
    print("\n🔑 セッションファイル")
    print(_check_sessions())

    # 3. 収集データ
    print("\n📦 収集データ")
    print(_check_collected())

    # 4. 日次カウンター
    print("\n📊 日次カウンター")
    print(_check_daily_counts())

    # 5. アカウント設定
    print("\n⚙️ アカウント設定")
    print(_check_config_paths())

    # 6. ツール類
    print("\n🔧 ツール類")
    print(f"  {_check_forcebindip()}")
    print(f"  {_check_playwright()}")

    # 7. ディスク使用量
    print("\n💾 ディスク使用量")
    print(_check_disk())

    # 8. 型チェック結果（簡易）
    print(f"\n🧪 品質")
    # mypy結果があれば
    mypy_ini = BASE / 'mypy.ini'
    pytest_dir = BASE / 'tests'
    print(f"  {OK} mypy.ini: {'あり' if mypy_ini.exists() else 'なし'}")
    test_count = len(list(pytest_dir.glob('test_*.py'))) if pytest_dir.exists() else 0
    print(f"  {OK} テスト: {test_count}ファイル")

    print(f"\n{'='*60}")
    print(f"  完了")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
