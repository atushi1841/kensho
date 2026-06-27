"""
Kensho Dashboard — Streamlit 可視化ダッシュボード
python -m streamlit run scripts/kensho_dashboard.py
"""
from __future__ import annotations

import json
from datetime import datetime, date
from pathlib import Path
from typing import Any

import streamlit as st

BASE: Path = Path(__file__).parent.parent
DATA_DIR: Path = BASE / 'data'

st.set_page_config(page_title='Kensho Dashboard', layout='wide')
st.title('🎯 Kensho Dashboard')
st.caption(f'最終更新: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')


def load_json(name: str) -> Any:
    p = DATA_DIR / name
    if p.exists():
        try:
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


# ── サイドバー ──
st.sidebar.header('📊 データ')
refresh = st.sidebar.button('🔄 更新')

# ── メイン: 3カラム ──
col1, col2, col3 = st.columns(3)

# === 1. 当選サマリー ===
with col1:
    st.subheader('🏆 当選サマリー')
    wins = load_json('wins.json')
    total_wins = len(wins)
    unclaimed = sum(1 for w in wins if not w.get('claimed', False))

    # 今月
    this_month = [w for w in wins if w.get('date', '').startswith(date.today().strftime('%Y-%m'))]

    st.metric('総当選数', total_wins, delta=len(this_month))
    st.metric('今月の当選', len(this_month))
    st.metric('未報告', unclaimed)

    # アカウント別
    if wins:
        st.subheader('アカウント別')
        by_account = {}
        for w in wins:
            by_account[w.get('account', '?')] = by_account.get(w.get('account', '?'), 0) + 1
        for acct, count in sorted(by_account.items(), key=lambda x: -x[1]):
            st.text(f'{acct}: {count}件')

# === 2. 賞品管理 ===
with col2:
    st.subheader('🎁 賞品管理')
    prizes = load_json('prizes.json')
    total_prizes = len(prizes)
    used = sum(1 for p in prizes if p.get('used', False))
    unused = total_prizes - used
    with_coupons = sum(1 for p in prizes if p.get('coupons'))

    st.metric('総賞品数', total_prizes)
    st.metric('使用済み', used)
    st.metric('未使用', unused)

    # 賞品タイプ別
    if prizes:
        st.subheader('賞品タイプ')
        types = {}
        for p in prizes:
            pt = p.get('prize_type', 'その他')
            types[pt] = types.get(pt, 0) + 1
        for pt, count in sorted(types.items(), key=lambda x: -x[1]):
            st.text(f'{pt}: {count}件')

    # 未使用クーポン
    if unused > 0:
        st.subheader('📋 未使用一覧')
        for p in prizes:
            if p.get('used'):
                continue
            coupon_codes = [c['code'] for c in p.get('coupons', [])]
            urls = p.get('urls', [])
            label = p.get('prize_type', '?')
            if p.get('prize_value'):
                label += f' [{p["prize_value"]}]'
            if coupon_codes:
                label += f' 🔑{", ".join(coupon_codes)}'
            st.text(f'• {label}')

# === 3. アカウント健全性 ===
with col3:
    st.subheader('🛡️ アカウント健全性')
    health = load_json('account_health.json')
    accounts = health.get('accounts', {})

    for key, info in accounts.items():
        status = info.get('status', 'unknown')
        icon = {'healthy': '✅', 'shadowbanned': '⚠️', 'error': '❌', 'unknown': '❓'}.get(status, '❓')
        tweets = info.get('tweet_count', 0)
        sb_strikes = info.get('consecutive_shadowbans', 0)
        st.text(f'{icon} {key}: {status}')
        st.caption(f'   tweets={tweets}, SB={sb_strikes}回')

    # フォロー状況
    st.subheader('👥 フォロー状況')
    follow_state = load_json('follow_state.json')
    accts = follow_state.get('accounts', {})
    for key, info in accts.items():
        last_count = info.get('last_follow_count', 0)
        last_unf = info.get('last_unfollow_count', 0)
        st.text(f'{key}: {last_count}フォロー')
        if last_unf:
            st.caption(f'   前回{last_unf}件解除')

# ── 下部: 当選詳細 ──
st.divider()
st.subheader('📝 当選詳細ログ')

if wins:
    for w in reversed(wins[-20:]):
        with st.expander(f'{w.get("date", "?")} @{w.get("from_user", "?")} - {w.get("text", "")[:50]}...'):
            st.write(f'**アカウント:** {w.get("account", "?")}')
            st.write(f'**受信日:** {w.get("date", "?")}')
            st.write(f'**送信者:** @{w.get("from_user", "?")} ({w.get("from_name", "")})')
            st.write(f'**賞品価格:** {w.get("prize_value", "不明")}')
            st.write('**テキスト:**')
            st.code(w.get("text", ""))
            claimed = '✅ 報告済み' if w.get('claimed') else '⏳ 未報告'
            st.write(f'**ステータス:** {claimed}')
else:
    st.info('当選記録がありません。Win Trackerを実行してください。')

# ── 実行方法 ──
st.divider()
st.caption('💡 更新: サイドバーの「更新」ボタンをクリック')
st.caption('🏃 手動更新: python scripts/kensho_win_tracker.py → python scripts/kensho_prize_manager.py')
