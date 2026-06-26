"""
Kensho Shadowban Checker — アカウント健全性自動監視
from:検索で各アカウントの可視性をチェック
shadowban検出時は自動で該当アカウントの応募を停止
"""
from __future__ import annotations

import asyncio, json
from datetime import datetime
from pathlib import Path
from typing import Any

BASE: Path = Path(__file__).parent.parent
DATA_DIR: Path = BASE / 'data'
HEALTH_FILE: Path = DATA_DIR / 'account_health.json'


def load_health() -> dict[str, Any]:
    if HEALTH_FILE.exists():
        try:
            with open(HEALTH_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {'accounts': {}, 'last_check': ''}


def save_health(health: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HEALTH_FILE, 'w', encoding='utf-8') as f:
        json.dump(health, f, ensure_ascii=False, indent=2)


def load_session(account_key: str) -> tuple[str, str]:
    config_path = BASE / 'config.yaml'
    if not config_path.exists():
        return '', ''
    import yaml
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    for acct in cfg.get('accounts', []):
        if acct['key'] == account_key:
            session_path = BASE / acct['session']
            if session_path.exists():
                with open(session_path, 'r', encoding='utf-8') as sf:
                    session_data = json.load(sf)
                cookies = {c['name']: c['value'] for c in session_data.get('cookies', [])}
                return cookies.get('auth_token', ''), cookies.get('ct0', '')
    return '', ''


async def check_account_shadowban(account_key: str) -> dict[str, Any]:
    """from:検索でアカウントの可視性をチェック"""
    from twscrape import API, gather

    result: dict[str, Any] = {
        'account': account_key,
        'status': 'unknown',
        'search_ok': False,
        'recent_tweet_found': False,
        'tweet_count': 0,
        'checked_at': datetime.now().isoformat(),
    }

    auth_token, ct0 = load_session(account_key)
    if not auth_token:
        result['status'] = 'no_session'
        return result

    try:
        api = API()
        cookie_str = f'auth_token={auth_token}; ct0={ct0}'
        await api.pool.add_account_cookies(f'shadow_check_{account_key}', cookie_str)

        # from: 検索で直近のツイートを検索
        tweets = await gather(api.search(f'from:@{account_key} lang:ja', limit=5))
        result['tweet_count'] = len(tweets)
        result['recent_tweet_found'] = len(tweets) > 0

        if result['recent_tweet_found']:
            result['status'] = 'healthy'
            result['search_ok'] = True
        else:
            # 別のクエリで再確認（display名で検索）
            tweets2 = await gather(api.search(f'{account_key}', limit=5))
            if len(tweets2) > 0:
                result['status'] = 'healthy'
                result['search_ok'] = True
            else:
                result['status'] = 'shadowbanned'

    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)[:100]

    return result


def should_pause_account(health: dict[str, Any], account_key: str) -> bool:
    """アカウントを停止すべきか判定"""
    acct = health.get('accounts', {}).get(account_key, {})
    if acct.get('status') == 'shadowbanned':
        # 2回連続でshadowbanなら停止
        strikes = acct.get('consecutive_shadowbans', 0)
        return strikes >= 2

    # エラーが3回連続なら停止
    if acct.get('status') == 'error':
        strikes = acct.get('consecutive_errors', 0)
        return strikes >= 3

    return False


def main() -> None:
    print(f'[ShadowbanChecker] {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print()

    health = load_health()
    accounts = health.get('accounts', {})
    account_keys: list[str] = ['atushi16', 'kudou', 'atushi1840', 'zin20120731']

    for key in account_keys:
        print(f'  [{key}] チェック中...')
        result = asyncio.run(check_account_shadowban(key))

        # 履歴を更新
        prev = accounts.get(key, {})
        prev_strikes_sb = prev.get('consecutive_shadowbans', 0)
        prev_strikes_err = prev.get('consecutive_errors', 0)

        if result['status'] == 'shadowbanned':
            result['consecutive_shadowbans'] = prev_strikes_sb + 1
            result['consecutive_errors'] = 0
        elif result['status'] == 'error':
            result['consecutive_shadowbans'] = prev_strikes_sb if result['status'] == 'error' else 0
            result['consecutive_errors'] = prev_strikes_err + 1
        else:
            result['consecutive_shadowbans'] = 0
            result['consecutive_errors'] = 0

        accounts[key] = result

        icon: str = '✅' if result['status'] == 'healthy' else '⚠️' if result['status'] == 'shadowbanned' else '❌'
        print(f'  {icon} {key}: {result["status"]}'
              f' (tweets={result["tweet_count"]},'
              f' sb={result.get("consecutive_shadowbans", 0)}連続)')

        pause = should_pause_account(health, key)
        if pause:
            print(f'    ⛔ 自動停止: {key} の応募を停止します')

    health['accounts'] = accounts
    health['last_check'] = datetime.now().isoformat()
    save_health(health)

    print(f'\n  保存完了 → {HEALTH_FILE}')

    # サマリー
    healthy = sum(1 for a in accounts.values() if a.get('status') == 'healthy')
    banned = sum(1 for a in accounts.values() if a.get('status') == 'shadowbanned')
    errors = sum(1 for a in accounts.values() if a.get('status') == 'error')
    paused = sum(1 for k in account_keys if should_pause_account(health, k))
    print(f'\n  健全: {healthy} | shadowban: {banned} | エラー: {errors} | 停止中: {paused}')


if __name__ == '__main__':
    main()
