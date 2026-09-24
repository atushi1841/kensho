#!/usr/bin/env bash
# BOTシグナル（自己修復リトライによる露出増幅）の日次監視 — 読み取り専用。
#
# 計測する2つのシグナル:
#   FAILED : "goto failed" 行数 = ブラウザ遷移失敗。self_heal の盲目的リトライで増幅していた主指標。
#            実測: 09-20=63 / 09-21=36 / 09-22=81 / 09-23=227 件/日
#   LOGIN  : "Xにログイン確認中" 行数 = ブラウザセッション起動回数（kensho/application/browser.py:924）。
#            セッション起動ごとに必ず1行出るため「ログイン試行」= 露出の代理指標。
#            実測: 09-20=54 / 09-21=40 / 09-22=67 / 09-23=108 件/日（リトライで3回転していた）
#   BURST  : 10分窓に何本のログイン確認が集中したか（最大値）。リトライ起因の増幅の直接シグナル。
#            正常時は 1（=1セッション1回）。09-23 は同一垢の再起動が連続し 4〜8 に達していた。
#
# 増幅の恒久対策は commit 4ef200d（failure ceiling の垢粒度化 + session/auth/dead_proxy の非リトライ化）。
# 本スクリプトは対策の効果を日次で測るだけで、応募ロジックには一切触れない。
#
# usage:
#   bash scripts/check_bot_signal.sh [YYYY-MM-DD] [--since HH:MM] [--amplification-only]
#     YYYY-MM-DD        対象日（省略時は今日）。ログは logs/auto_YYYYMMDD.log（日次ローテーション）
#     --since HH:MM     その日時以降の行だけを数える（修正投入後の窓を測る用）
#     --amplification-only  cron監視用: 閾値超過でも BURST<3 かつ FAILED<閾値 なら exit 0
#                          （LOGIN は「セッション起動数」であり設計上の下限があるため単独では警報にしない）
#
# exit: 0=基準内 / 1=基準超過（要確認） / 2=対象ログなし
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAILED_MAX=5    # goto failed < 5 件/日
LOGIN_MAX=10    # ログイン試行 < 10 件/日
BURST_MAX=2     # 10分窓の最大集中（正常=1）

DATE=""
SINCE=""
AMP_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --since)             shift_next_since=1 ;;
        --amplification-only) AMP_ONLY=1 ;;
        --*)                 echo "unknown option: $arg" >&2; exit 64 ;;
        *)                   if [ "${shift_next_since:-0}" = "1" ]; then SINCE="$arg"; shift_next_since=0; else DATE="$arg"; fi ;;
    esac
done
[ -n "$DATE" ] || DATE="$(date +%F)"
YMD="${DATE//-/}"
LOG="${REPO_ROOT}/logs/auto_${YMD}.log"

if [ ! -f "$LOG" ]; then
    echo "check_bot_signal: no log for ${DATE} (${LOG})"
    exit 2
fi

count() {  # $1=grepパターン -> 件数（0件でも失敗にしない）
    grep -c -- "$1" "$LOG" 2>/dev/null || true
}

if [ -n "$SINCE" ]; then
    SINCE_TS="${DATE} ${SINCE}"
    # 直近に現れたタイムスタンプ以降のみを対象にする（ログは行頭タイムスタンプ付き）
    FAILED=$(awk -v ts="$SINCE_TS" '/^[0-9]{4}-[0-9]{2}-[0-9]{2} /{cur=$1" "$2} /goto failed/{if(cur>=ts)f++} END{print f+0}' "$LOG")
    LOGIN=$(awk  -v ts="$SINCE_TS" '/^[0-9]{4}-[0-9]{2}-[0-9]{2} /{cur=$1" "$2} /Xにログイン確認中/{if(cur>=ts)l++} END{print l+0}' "$LOG")
else
    FAILED=$(count "goto failed")
    LOGIN=$(count "Xにログイン確認中")
fi

# 10分窓の最大集中（ログイン確認の同時多発 = リトライ増幅の直接シグナル）
BURST=$(awk -v ts="${SINCE:+${DATE} ${SINCE}}" '
    function m(hhmm,   a) { split(hhmm, a, ":"); return a[1]*60 + a[2] }
    /^[0-9]{4}-[0-9]{2}-[0-9]{2} / { cur = $1 " " $2 }
    /Xにログイン確認中/ { if (ts == "" || cur >= ts) { t = m(substr($2, 1, 5)); if (t in seen) seen[t]++; else seen[t] = 1 } }
    END {
        best = 0
        for (k in seen) { s = k + 0; c = 0
            for (j in seen) { jj = j + 0; if (jj >= s && jj < s + 10) c += seen[j] }
            if (c > best) best = c
        }
        print best
    }' "$LOG")

echo "check_bot_signal ${DATE}${SINCE:+ (since ${SINCE})} log=${LOG#${REPO_ROOT}/}"
echo "FAILED=${FAILED} (しきい値 <${FAILED_MAX})  LOGIN=${LOGIN} (しきい値 <${LOGIN_MAX})  BURST=${BURST} (しきい値 <=${BURST_MAX})"

rc=0
if [ "$FAILED" -lt "$FAILED_MAX" ]; then
    echo "  [PASS] goto failed < ${FAILED_MAX}/日"
else
    echo "  [FAIL] goto failed >= ${FAILED_MAX}/日 → 自己修復リトライの増幅を疑う（data/self_heal_state.json の ceilings と [SELF-HEAL] 行を確認）"
    rc=1
fi

if [ "$AMP_ONLY" = "1" ]; then
    # 監視モード: 露出の絶対数ではなく「増幅」（失敗多発 or リトライ集中）だけを警報にする
    if [ "$BURST" -gt "$BURST_MAX" ]; then
        echo "  [FAIL] 10分窓のセッション起動集中が ${BURST} 件（正常は1。リトライ再起動の疑い）"
        rc=1
    fi
    [ "$rc" = "0" ] && echo "  [PASS] 増幅シグナルなし（LOGIN は設計上のセッション起動数であり単独では警報にしない）"
else
    if [ "$LOGIN" -lt "$LOGIN_MAX" ]; then
        echo "  [PASS] ログイン試行 < ${LOGIN_MAX}/日"
    else
        echo "  [FAIL] ログイン試行 ${LOGIN} >= ${LOGIN_MAX}/日 → セッション起動数の下限（1垢1セッション=1行）を確認。BURST=${BURST} が 1〜2 なら増幅ではなく運用量"
        rc=1
    fi
fi

exit $rc
