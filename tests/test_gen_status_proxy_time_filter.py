def test_counterproof_implementation_removed_should_fail() -> None:
    """実装のフィルタ条件を無効化したコピーで gen_status_data.py を読み込むと、
    test_skips_row_before_gen_start 相当が赤になることを実測。
    """
    import re
    from datetime import datetime, date, timedelta, timezone
    
    # 1. 元のフィルタを読み込む（load_filter経由で）
    from scripts.verify_status_proxy_same_tick import load_filter
    real_filter = load_filter()

    # 2. gen_status_data.py から _filter_proxy_check_rows 関数のソースを取得
    with open("/mnt/d/Project2/kensho/scripts/gen_status_data.py", "r") as f:
        lines = f.readlines()
    
    # 関数の開始と終了を見つける
    start_line = None
    end_line = None
    indent_level = None
    
    for i, line in enumerate(lines):
        if line.strip().startswith("def _filter_proxy_check_rows("):
            start_line = i
            # インデントレベルを取得
            indent_level = len(line) - len(line.lstrip())
        elif start_line is not None and line.strip() and not line.startswith(" " * (indent_level + 1)) and not line.startswith("\t"):
            # 次のレベルと同じかそれ以下のインデントの行が来たら関数終了
            if not line.startswith(" " * indent_level) and not line.startswith("\t"):
                end_line = i
                break
    
    if end_line is None:
        end_line = len(lines)
    
    # 関数のソースを取得
    func_lines = lines[start_line:end_line]
    func_source = "".join(func_lines)
    
    # gen_start チェックを削除したバージョンを作成
    # "if prev_ts is None or prev_ts < gen_start:" を "if prev_ts is None:" に変更
    modified_source = func_source.replace(
        "if prev_ts is None or prev_ts < gen_start:",
        "if prev_ts is None:  # gen_start チェックを削除"
    )
    
    # 3. 元のインポート文を維持するモジュールを作成
    # 必要なインポートを抽出
    import_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("from datetime import") or stripped.startswith("import ") or stripped.startswith("from collections import") or stripped.startswith("from typing import"):
            import_lines.append(line)
        elif stripped and not line.startswith(" ") and not line.startswith("\t") and not stripped.startswith("#") and not stripped.startswith("JST"):
            # インポートセクション終了（実際のコードが始まるとき）
            if import_lines and (stripped.startswith("def ") or stripped.startswith("JST =") or stripped.startswith("_audit_jst_date")):
                break
    
    # タイムゾーン定数も含める
    jst_lines = []
    for line in lines:
        if line.strip().startswith("JST ="):
            jst_lines.append(line)
            break
    
    # モジュールソースを作成
    module_source = "".join(import_lines) + "".join(jst_lines) + modified_source
    
    # 4. モジュールを実行して関数を取得
    ns = {}
    exec(module_source, ns)
    counterproof_filter = ns["_filter_proxy_check_rows"]

    # 5. test_skips_row_before_gen_start 相当のテストデータでフィルタを実行
    txt = (
        "[2026-09-25 04:15:01] 今回 spawn: 4 垢（即終了：処理本体は各垢が並列で実行）\\n"
        "Proxy zin20120731:1084 is dead\\n"
        "WiFi reconnect failed – adapter zin_AW6povo still 'Disconnected'\\n"
        "[PROXY-CHECK] alive=[1081, 1082, 1085] dead=[1084] restored=0 (16.2s)\\n"
    )
    gen = datetime(2026, 9, 25, 4, 30, 0)

    # 元のフィルタでテスト（この行はスキップされるはず）
    result_ts_real, alive_real, dead_real, restored_real, best_real = real_filter(txt, gen, None)

    # カウンタープルーフフィルタでテスト（この行はスキップされないはず）
    result_ts_cp, alive_cp, dead_cp, restored_cp, best_cp = counterproof_filter(txt, gen, None)

    # 6. 結果が異なることを確認
    # 元のフィルタ: 行はスキップされるので result_ts_real is None
    # カウンタープルーフフィルタ: 行はスキップされないので result_ts_cp is not None
    
    # 元のフィルタは行をスキップするはず
    assert result_ts_real is None, f"Real filter should skip row, got result_ts={result_ts_real}"

    # カウンタープルーフフィルタは行をスキップしないはず（実装が削除されているため）
    assert result_ts_cp is not None, f"Counterproof filter should NOT skip row (implementation removed), got result_ts={result_ts_cp}"

    # さらに詳細なチェック：カウンタープルーフフィルタは実際の行の値を返すはず
    assert result_ts_cp == gen, f"Counterproof filter should return the row timestamp, got {result_ts_cp}"
    assert alive_cp == [1081, 1082, 1085], f"Counterproof filter should return alive values, got {alive_cp}"
    assert dead_cp == [1084], f"Counterproof filter should return dead values, got {dead_cp}"
    assert restored_cp == 0, f"Counterproof filter should return restored value, got {restored_cp}"