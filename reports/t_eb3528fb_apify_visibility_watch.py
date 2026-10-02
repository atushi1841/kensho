#!/usr/bin/env python3
# Apify可視性ウォッチ: 通常ストア検索に自分のactorが何本出るか（KYCゲートの10秒テスト）
# 出力 "visible=N" — Nが0超になったらKYC通過=全actorがストアに出現した合図
#
# v2 (t_eb3528fb / 2026-09-30): Apify API timeout値・再試行を追加。
#   1) 1 attempt あたりの timeout は APIFY_WATCH_TIMEOUT 秒（既定40）に分離。
#   2) 指数バックオフで **2回再試行**（計3 attempt）: 待機 2s, 4s + jitter。
#      9/30 実測では 40s で切れて visible=ERROR <urlopen error timed out> になり、
#      monitorハッシュが変化して agent run を誘発したため、ここをまず安定させる。
#   3) 配信失敗フォールバック: 前回 run の last_delivery_error が残っている場合のみ
#      "redelivery_pending=1" を追記する。monitor 出力のハッシュが前回と必ず変わる
#      ため次回 run が実行され、その run の配信が欠損した通知を補う（次回runで再配信）。
#      配信成功で last_delivery_error がクリアされればこの行も消え、通常運用に戻る。
#   4) 監視スクリプトは終了コードを判定に使わず、1行の有無＋ハッシュで判定するため、
#      最終失敗時も必ず1行を出して終了コード0を返す。
import json
import os
import random
import ssl
import sys
import time
import urllib.error
import urllib.request

APIFY_STORE_URL = "https://api.apify.com/v2/store?limit=1000&username=fruitful_quintessence"
JOB_ID = "b381e7117f9d"     # apify-visibility-watch（このスクリプトの monitor 元ジョブ）
MAX_ATTEMPTS = 3          # 初回 + 再試行2回
BACKOFF_BASE = 2.0        # 2.0s, 4.0s （+ 0〜0.5s jitter）


def _timeout() -> float:
    try:
        return max(1.0, float(os.environ.get("APIFY_WATCH_TIMEOUT", "40")))
    except (TypeError, ValueError):
        return 40.0


def _fetch(timeout: float) -> int:
    ctx = ssl.create_default_context()
    # 注意: 無認証だと count は正しくても items が空になる（9/8実測バグ）。
    # count フィールドを読むこと。
    req = urllib.request.Request(
        APIFY_STORE_URL,
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        data = json.load(resp).get("data", {})
    return int(data.get("count", 0) or 0)


def _fetch_with_retry():
    """3 attempt・指数バックオフ。戻り値は (成功時 count / 失敗時 None, 最終例外)。"""
    last_exc = None
    timeout = _timeout()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return _fetch(timeout), None
        except Exception as exc:  # noqa: BLE001 - monitor は1行を必ず出す必要がある
            last_exc = exc
            if attempt >= MAX_ATTEMPTS:
                break
            wait = BACKOFF_BASE * (2 ** (attempt - 1)) + random.uniform(0.0, 0.5)
            # 4xx(408/429除く)は再試行しても直らないため早めに諦める
            code = getattr(exc, "code", None)
            if isinstance(code, int) and 400 <= code < 500 and code not in (408, 429):
                break
            print(
                f"apify_visibility_watch: attempt {attempt}/{MAX_ATTEMPTS} failed "
                f"({type(exc).__name__}: {str(exc)[:60]}), retry in {wait:.1f}s",
                file=sys.stderr,
            )
            time.sleep(wait)
    return None, last_exc


def _job_delivery_error(path: str) -> bool:
    """指定した jobs.json にこのジョブの last_delivery_error が残っているか。"""
    with open(path, encoding="utf-8") as fh:
        jobs = json.load(fh)
    jobs = jobs.get("jobs", jobs) if isinstance(jobs, dict) else jobs
    for job in jobs:
        if job.get("id") == JOB_ID:
            return bool(str(job.get("last_delivery_error") or "").strip())
    return False


def _redelivery_pending() -> bool:
    """前回 run の配信が失敗しているか（成功すると hermes 側でクリアされる）。

    パス解決は「スクリプト自身の属するプロファイル」を常に優先する。HERMES_HOME を
    先に見ると、別プロファイル（例: kensho-revenue-worker）から実行された際に
    このジョブを含まない jobs.json を読んで False を返し、再配信トリガーが
    無言で消える（t_eb3528fb 実測バグ）。HERMES_HOME は第2候補としてのみ使う。
    """
    script_home = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [os.path.join(script_home, "cron", "jobs.json")]
    env_home = os.environ.get("HERMES_HOME")
    if env_home:
        candidates.append(os.path.join(env_home, "cron", "jobs.json"))
    for path in candidates:
        try:
            if _job_delivery_error(path):
                return True
        except Exception:
            # 監視を配信状態の読み取り失敗で止めない（次の候補へ）
            continue
    return False


def main() -> int:
    count, exc = _fetch_with_retry()
    if count is not None:
        print(f"visible={count}")
    else:
        # 3 attempt 全滅。文言は 9/30 以前と同一書式で残す（後段のレポート互換）
        print("visible=ERROR", str(exc)[:60] if exc is not None else "unknown")
    if _redelivery_pending():
        # 前回の通知が届いていない → ハッシュ変化で次回 run を起こし、再配信させる
        print("redelivery_pending=1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
