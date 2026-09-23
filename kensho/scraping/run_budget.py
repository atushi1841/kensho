"""収集run単位の実行時間予算（deadline）— t_b64c35ea.

背景（実測 2026-09-21〜23）:
    毎時収集(kensho-collect-only.sh)は /tmp/kensho-collect.lock の flock を
    collect() を実行する子プロセスが保持したまま終了するため、1run が長時間化すると
    後続の毎時スロットが「⚠️ 前回の収集がまだ継続中 → スキップ」で丸ごと欠落する。
    9/21=6件 / 9/22=6件 / 9/23=6件（14スロット中）がスキップ、13:00run=118分、
    21:00run は 2.5 時間超まで継続していた。

方針:
    1run の実行時間上限(max_run_seconds)を設け、超過したら「残ソースの打ち切り」だけを行う。
    プロセスは強制終了せず、通常の収集後フロー（マージ → safe_save_json）を必ず通す
    ＝ それまでに収集できた分は部分保存される（データを捨てない）。
"""

from __future__ import annotations

import time
from collections.abc import Callable

#: config.yaml `collection.max_run_seconds` 未設定時の既定上限（秒）。
#: 25分に設定している理由: 収集単体の通常所要は13〜25分で、事後処理（保存・レポート・
#: ヘルス保存）に残り5分を残せば 1run 30分未満（後続スロットを欠落させない目安）に収まる。
DEFAULT_MAX_RUN_SECONDS: float = 1500.0

#: ログ・JSON で機械判定に使う打ち切りマーカー（grep 可能であること）。
MARKER: str = "⏱ [DEADLINE]"

#: 時刻取得関数（テストで差し替え可能にするための型）。
Clock = Callable[[], float]


class RunBudget:
    """1run の実行時間予算。経過時間を単調時計で測り、上限到達を報告する。"""

    def __init__(self, max_seconds: float = DEFAULT_MAX_RUN_SECONDS, *, clock: Clock = time.monotonic) -> None:
        self.max_seconds: float = float(max_seconds)
        self._clock: Clock = clock
        self._start: float = clock()
        #: 打ち切りが発生した phase 名（重複なし・発生順）。result JSON にも記録する。
        self.expired_phases: list[str] = []

    @property
    def disabled(self) -> bool:
        """0 以下なら時間制限なし（従来挙動）。"""
        return self.max_seconds <= 0

    @property
    def elapsed(self) -> float:
        return self._clock() - self._start

    @property
    def remaining(self) -> float:
        if self.disabled:
            return float("inf")
        return max(0.0, self.max_seconds - self.elapsed)

    def expired(self) -> bool:
        """上限に到達したか（disabled なら常に False）。"""
        if self.disabled:
            return False
        return self.elapsed >= self.max_seconds

    def note(self, phase: str) -> None:
        """打ち切り phase を記録（重複は無視）。"""
        if phase not in self.expired_phases:
            self.expired_phases.append(phase)


def check_budget(budget: RunBudget, phase: str, out: Callable[[str], None]) -> bool:
    """予算超過なら phase を打ち切り対象として記録・ログして True を返す。

    呼び出し側は True のとき「その phase のネットワーク処理を行わず skip」する。
    ログは同一 phase につき1回だけ出す（毎ループで出してログを埋めない）。
    """
    if not budget.expired():
        return False
    is_new: bool = phase not in budget.expired_phases
    budget.note(phase)
    if is_new:
        out(
            f"{MARKER} 実行時間上限 {budget.max_seconds:.0f}秒 到達 "
            f"（経過 {budget.elapsed:.0f}秒）→ {phase} を打ち切り・収集済み分は部分保存"
        )
    return True
