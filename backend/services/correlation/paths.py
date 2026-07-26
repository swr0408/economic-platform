# -*- coding: utf-8 -*-
"""共通パス解決 (リポジトリルート基準)。"""
from pathlib import Path

# backend/services/correlation/paths.py -> parents[3] = repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "backend"
CACHE_DIR = BACKEND / "data" / "cache"
SEASONALITY_INPUT = BACKEND / "data" / "manual_update" / "seasonality" / "input"
REPORTS_ROOT = BACKEND / "data" / "reports" / "correlation"


def as_of_dir(as_of: str) -> Path:
    return REPORTS_ROOT / as_of


def latest_pointer() -> Path:
    """最新スナップショットの as_of 文字列を記録する小ファイル。"""
    return REPORTS_ROOT / "LATEST"
