#!/usr/bin/env python3
"""Kensho Single Apply — ForceBindIPで指定インターフェース経由で1垢の応募を実行"""
from __future__ import annotations
import sys, os, json, time
from datetime import datetime

# ── cp932ガード + コンソール非表示（共通ユーティリティ経由）──
sys.path.insert(0, os.path.dirname(__file__))
from core.encoding import guard_stdio, hide_console
guard_stdio()
hide_console()
from application.applier import apply_for_account

if __name__ == '__main__':
    from argparse import ArgumentParser
    _p = ArgumentParser(description='Kensho 単一アカウント応募')
    _p.add_argument('account', help='アカウントキー (例: atushi16)')
    _p.add_argument('max_n', type=int, help='最大処理件数')
    _p.add_argument('--dry-run', action='store_true', help='実際に応募せずログのみ')
    _args = _p.parse_args()
    key = _args.account
    max_n = _args.max_n

    # ── 結果ファイルのパスを先に決定（クラッシュ時も書き込めるように）──
    result_dir = os.path.join(os.path.dirname(__file__), 'logs',
                              datetime.now().strftime('%Y-%m-%d'))
    os.makedirs(result_dir, exist_ok=True)
    result_file = os.path.join(result_dir, 'apply_result_{}.json'.format(key))
    
    # 全例外をキャッチして必ず結果ファイルを書く
    try:
        # ── PIDロック: 同一垢の多重起動防止 (Windows対応) ──
        LOCK_DIR = os.path.join(os.path.dirname(__file__), 'data', 'locks')
        os.makedirs(LOCK_DIR, exist_ok=True)
        lock_path = os.path.join(LOCK_DIR, f'apply_{key}.pid')

        # 既存ロック確認
        if os.path.exists(lock_path):
            try:
                with open(lock_path) as f:
                    old_pid = int(f.read().strip())
                import psutil
                if psutil.pid_exists(old_pid):
                    result = {'account': key, 'success': 0, 'errors': 0, 'info': f'PID lock: {old_pid} running'}
                    with open(result_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f)
                    print(f"[LOCK] 別インスタンスが実行中 (PID {old_pid}, {key}) → 終了")
                    sys.exit(0)
            except Exception:
                import traceback
                print(f"[LOCK] 古いPIDロック読み込み失敗: {traceback.format_exc()[-100:]}", flush=True)
                pass
            try:
                os.remove(lock_path)
            except Exception:
                print(f"[LOCK] ロックファイル削除失敗（{lock_path}）", flush=True)
                pass

        with open(lock_path, 'w') as f:
            f.write(str(os.getpid()))

        def _cleanup() -> None:
            try:
                if os.path.exists(lock_path):
                    os.remove(lock_path)
            except Exception:
                pass
        import atexit
        atexit.register(_cleanup)

        # ── 事前チェック: 未応募がなければ即終了（ブラウザ起動前に）──
        col_path = os.path.join(os.path.dirname(__file__), 'data', 'collected.json')
        try:
            if os.path.exists(col_path):
                with open(col_path, 'r', encoding='utf-8') as f:
                    col_data = json.load(f)
                items = col_data.get('collected', [])
                unapplied = [i for i in items if i.get('applied', {}).get(key) is None]
                if not unapplied:
                    result = {'account': key, 'success': 0, 'errors': 0, 'info': 'no unapplied items'}
                    with open(result_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f)
                    print(f"[Kensho] {key}: 未応募なし → 早期終了")
                    sys.exit(0)
        except Exception as e:
            import traceback
            print(f"[WARN] 未応募チェック失敗（collected.json破損?）: {e}", flush=True)
            print(f"  {traceback.format_exc()[-200:]}", flush=True)
            pass

        # ForceBindIPがstdoutを食うので、結果はファイルに書く
        succ, err = apply_for_account(key, max_n)
        result = {'account': key, 'success': succ, 'errors': err}
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        result = {'account': key, 'success': 0, 'errors': 1, 
                  'exception': str(e), 'traceback': traceback.format_exc()[-500:]}

    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(result, f)

    print('RESULT: {} success, {} errors'.format(result['success'], result['errors']))
