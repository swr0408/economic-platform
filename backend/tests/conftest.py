"""
backend/tests 用 pytest conftest

- backend/ ディレクトリを sys.path 先頭に追加することで、
  既存コードと同じ `from core.xxx import ...` 形式のインポートが効くようにする
- backend/__init__.py が存在するため、`backend.core.xxx` と `core.xxx` の二重ロードを
  避けるために、tests パッケージ自体は通常の名前空間では import されない前提とする
"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_BACKEND_STR = str(_BACKEND_DIR)
if _BACKEND_STR not in sys.path:
    sys.path.insert(0, _BACKEND_STR)
