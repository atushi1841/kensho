"""Kensho - 懸賞自動応募システム"""

from __future__ import annotations

import os
import sys

# kensho/ を sys.path に追加（内部の from kensho.core.xxx 等の解決用）
_kensho_dir = os.path.dirname(__file__)
if _kensho_dir not in sys.path:
    sys.path.insert(0, _kensho_dir)
