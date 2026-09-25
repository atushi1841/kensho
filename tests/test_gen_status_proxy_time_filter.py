def test_counterproof_implementation_removed_should_fail() -> None:
    """実装のフィルタ条件を無効化したコピーで gen_status_data.py を読み込むと、
    test_skips_row_before_gen_start 相当が赤になることを実測。

    2026-09-25 修正（収益化Worker・実測）: 旧実装は関数ソースを行番号で切り出していたが、
    `indent_level` が 0（トップレベル def）のとき `line.startswith(" " * indent_level)` が
    常に True になり終端判定が絶対に成立せず、**ファイル残り全体**を切り出していた。
    gen_status_data.py 内で本関数がファイル末尾でなくなった時点で、切り出し範囲に
    モジュール直下の `result[...]` 代入が混入し
    `NameError: name 'result' is not defined`（<string>:173）で落ちる＝
    counterproof が「実装を検査せず赤」という偽の赤になっていた。
    → ast で関数ノードだけを取り出す方式（scripts/verify_status_proxy_same_tick.load_filter と同型）に統一。
    """
    import ast
    from datetime import datetime

    # 1. 元のフィルタを読み込む（load_filter経由で）
    from scripts.verify_status_proxy_same_tick import load_filter

    real_filter = load_filter()

    # 2. gen_status_data.py から _filter_proxy_check_rows の関数ノードだけを ast で取り出す
    with open("/mnt/d/Project2/kensho/scripts/gen_status_data.py", encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src)
    fn_node = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "_filter_proxy_check_rows"
    )
    func_source = ast.get_source_segment(src, fn_node)
    assert func_source is not None and "def _filter_proxy_check_rows(" in func_source
    # 切り出しが関数1つに閉じていること（モジュール直下コードの混入なし）
    assert "result[" not in func_source, "関数ソースにモジュール直下コードが混入している"

    # 3. gen_start チェックを削除したバージョンを作成
    # "if prev_ts is None or prev_ts < gen_start:" を "if prev_ts is None:" に変更
    modified_source = func_source.replace(
        "if prev_ts is None or prev_ts < gen_start:",
        "if prev_ts is None:  # gen_start チェックを削除",
    )
    assert modified_source != func_source, "counterproof 用の置換が当たっていない（実装が変わった）"

    # 4. モジュールとして実行して関数を取得（datetime と re だけ与えれば動く）
    ns: dict = {}
    exec("from datetime import datetime\nimport re\n\n" + modified_source, ns)  # noqa: S102
    counterproof_filter = ns["_filter_proxy_check_rows"]

    # 5. test_skips_row_before_gen_start 相当のテストデータ（実改行で組み立てる）
    txt = (
        "[2026-09-25 04:15:01] 今回 spawn: 4 垢（即終了：処理本体は各垢が並列で実行）\n"
        "Proxy zin20120731:1084 is dead\n"
        "WiFi reconnect failed – adapter zin_AW6povo still 'Disconnected'\n"
        "[PROXY-CHECK] alive=[1081, 1082, 1085] dead=[1084] restored=0 (16.2s)\n"
    )
    gen = datetime(2026, 9, 25, 4, 30, 0)
    row_ts = datetime(2026, 9, 25, 4, 15, 1)

    # 元のフィルタでテスト（この行はスキップされるはず）
    result_ts_real, alive_real, dead_real, restored_real, best_real = real_filter(txt, gen, None)

    # カウンタープルーフフィルタでテスト（この行はスキップされないはず）
    result_ts_cp, alive_cp, dead_cp, restored_cp, best_cp = counterproof_filter(txt, gen, None)

    # 6. 結果が異なることを確認
    # 元のフィルタは行をスキップするはず
    assert result_ts_real is None, f"Real filter should skip row, got result_ts={result_ts_real}"

    # カウンタープルーフフィルタは行をスキップしないはず（実装が削除されているため）
    assert result_ts_cp is not None, (
        "Counterproof filter should NOT skip row (implementation removed), "
        f"got result_ts={result_ts_cp}"
    )

    # さらに詳細なチェック：カウンタープルーフフィルタは実際の行の値を返すはず
    # （返るのは直前タイムスタンプ行の時刻。gen ではない）
    assert result_ts_cp == row_ts, f"Counterproof filter should return the row timestamp, got {result_ts_cp}"
    assert alive_cp == [1081, 1082, 1085], f"Counterproof filter should return alive values, got {alive_cp}"
    assert dead_cp == [1084], f"Counterproof filter should return dead values, got {dead_cp}"
    assert restored_cp == 0, f"Counterproof filter should return restored value, got {restored_cp}"
