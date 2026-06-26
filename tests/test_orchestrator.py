"""
Tests for orchestrator.py — should_collect / load_state / save_state
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Safe import ──
# orchestrator.py にはモジュールレベルの副作用（PIDロック、
# guard_stdio()呼び出し、ディレクトリ作成）があるため、
# それらがテスト実行時に発動しないよう事前にパッチ。
with patch('os.makedirs'), \
     patch('builtins.open', mock_open(read_data="99999")), \
     patch('sys.exit'):
    import orchestrator
    from orchestrator import should_collect, load_state, save_state


class TestShouldCollect:
    """should_collect: 現在時刻が収集時刻の範囲内か（±5分）"""

    def test_exact_match(self) -> None:
        """時刻が完全一致 → True"""
        assert should_collect("10:00", ["10:00"]) is True

    def test_within_5_minutes_plus(self) -> None:
        """+3分 → True"""
        assert should_collect("10:03", ["10:00"]) is True

    def test_within_5_minutes_minus(self) -> None:
        """-3分 → True"""
        assert should_collect("09:57", ["10:00"]) is True

    def test_boundary_plus_5(self) -> None:
        """ちょうど+5分 → True（境界値）"""
        assert should_collect("10:05", ["10:00"]) is True

    def test_boundary_minus_5(self) -> None:
        """ちょうど-5分 → True（境界値）"""
        assert should_collect("09:55", ["10:00"]) is True

    def test_outside_plus_6(self) -> None:
        """+6分 → False"""
        assert should_collect("10:06", ["10:00"]) is False

    def test_outside_minus_6(self) -> None:
        """-6分 → False"""
        assert should_collect("09:54", ["10:00"]) is False

    def test_multiple_times_second_matches(self) -> None:
        """複数の収集時刻のうち2つ目にマッチ → True"""
        assert should_collect("14:30", ["10:00", "14:30", "20:00"]) is True

    def test_multiple_times_none_match(self) -> None:
        """複数の収集時刻のいずれにもマッチしない → False"""
        assert should_collect("12:00", ["10:00", "14:30", "20:00"]) is False

    def test_empty_times(self) -> None:
        """収集時刻リストが空 → False"""
        assert should_collect("10:00", []) is False

    def test_single_minute_exact(self) -> None:
        """1分差 (±1) は全パターンTrue"""
        assert should_collect("10:01", ["10:00"]) is True
        assert should_collect("09:59", ["10:00"]) is True

    def test_cross_midnight_not_relevant(self) -> None:
        """23:55 と 00:00 は差分が23時間55分 > 5 → False（日付跨ぎ非対応）"""
        assert should_collect("23:55", ["00:00"]) is False
        assert should_collect("00:00", ["23:55"]) is False


class TestStateLoadSave:
    """load_state / save_state: 状態ファイルの読み書き"""

    def test_load_empty(self, monkeypatch) -> None:
        """ファイルがない → {'last_processed': {}}"""
        tmpdir = tempfile.mkdtemp()
        monkeypatch.setattr(
            orchestrator, 'STATE_FILE',
            os.path.join(tmpdir, 'orchestrator_state.json'),
        )
        state = load_state()
        assert state == {'last_processed': {}}

    def test_save_and_load(self, monkeypatch) -> None:
        """保存して読み直せる"""
        tmpdir = tempfile.mkdtemp()
        state_file = os.path.join(tmpdir, 'orchestrator_state.json')
        monkeypatch.setattr(orchestrator, 'STATE_FILE', state_file)

        test_data = {'last_processed': {'acct1': '2026-06-24:10:00'}}
        save_state(test_data)
        loaded = load_state()
        assert loaded == test_data

    def test_save_and_load_multiple_accounts(self, monkeypatch) -> None:
        """複数アカウントの状態を保存→読込"""
        tmpdir = tempfile.mkdtemp()
        state_file = os.path.join(tmpdir, 'orchestrator_state.json')
        monkeypatch.setattr(orchestrator, 'STATE_FILE', state_file)

        test_data = {
            'last_processed': {
                'acct1': '2026-06-24:10:00',
                'acct2': '2026-06-24:14:30',
                'acct3': '2026-06-24:20:00',
            }
        }
        save_state(test_data)
        loaded = load_state()
        assert loaded == test_data

    def test_save_and_load_empty_state(self, monkeypatch) -> None:
        """空の状態で保存→読込"""
        tmpdir = tempfile.mkdtemp()
        state_file = os.path.join(tmpdir, 'orchestrator_state.json')
        monkeypatch.setattr(orchestrator, 'STATE_FILE', state_file)

        test_data = {'last_processed': {}}
        save_state(test_data)
        loaded = load_state()
        assert loaded == test_data

    def test_load_corrupted_file(self, monkeypatch) -> None:
        """壊れたJSON → {'last_processed': {}}（警告出力）"""
        tmpdir = tempfile.mkdtemp()
        state_file = os.path.join(tmpdir, 'orchestrator_state.json')
        monkeypatch.setattr(orchestrator, 'STATE_FILE', state_file)

        # 不正なJSONを書き込む
        with open(state_file, 'w', encoding='utf-8') as f:
            f.write('not-json{broken')

        state = load_state()
        assert state == {'last_processed': {}}

    def test_load_file_with_extra_fields(self, monkeypatch) -> None:
        """last_processed以外のフィールドがあっても保持される"""
        tmpdir = tempfile.mkdtemp()
        state_file = os.path.join(tmpdir, 'orchestrator_state.json')
        monkeypatch.setattr(orchestrator, 'STATE_FILE', state_file)

        test_data = {
            'last_processed': {'acct1': '2026-06-24:10:00'},
            'some_extra': True,
            'version': 2,
        }
        save_state(test_data)
        loaded = load_state()
        assert loaded == test_data

    def test_file_is_pretty_printed(self, monkeypatch) -> None:
        """JSONがindent=2で保存される"""
        tmpdir = tempfile.mkdtemp()
        state_file = os.path.join(tmpdir, 'orchestrator_state.json')
        monkeypatch.setattr(orchestrator, 'STATE_FILE', state_file)

        save_state({'last_processed': {'a': 'b'}})
        with open(state_file, 'r', encoding='utf-8') as f:
            raw = f.read()
        # prettified → 改行とインデントがある
        assert '  ' in raw
        assert '\n' in raw
