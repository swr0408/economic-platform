# -*- coding: utf-8 -*-
"""
相関・先行性レポート 配信エンドポイント (master 限定)。

    GET /api/reports/correlation                 - 最新スナップショットの manifest
    GET /api/reports/correlation/section/{id}    - セクション Markdown
    GET /api/reports/correlation/download/{name} - CSV ダウンロード

設計:
- マスター限定を **サーバ側で強制** (require_role("master"))。フロント隠蔽に依存しない。
- このルーターは pandas/statsmodels を import しない。**生成済みファイルを読むだけ**。
  重い解析はオフライン CLI (scripts/correlation_analysis/run.py) が担当。
- パストラバーサル防止のため section_id / name を厳格バリデーション。
"""
import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse

try:
    from backend.core.auth.dependencies import require_role
    from backend.core.auth.models import ROLE_MASTER, User
except ImportError:
    from core.auth.dependencies import require_role
    from core.auth.models import ROLE_MASTER, User

# レポート成果物のルート (services.correlation.paths と同一の場所)
_REPORTS_ROOT = Path(__file__).resolve().parents[1] / "data" / "reports" / "correlation"

_require_master = require_role(ROLE_MASTER)

_ID_RE = re.compile(r"^[a-z0-9_]+$")
_CSV_RE = re.compile(r"^[A-Za-z0-9_]+\.csv$")
_ASOF_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")

router = APIRouter(tags=["CorrelationReport"])


def _resolve_as_of(as_of: str | None) -> str:
    if as_of:
        if not _ASOF_RE.match(as_of):
            raise HTTPException(status_code=400, detail="invalid as_of")
        if not (_REPORTS_ROOT / as_of / "manifest.json").exists():
            raise HTTPException(status_code=404, detail="snapshot not found")
        return as_of
    latest = _REPORTS_ROOT / "LATEST"
    if not latest.exists():
        raise HTTPException(status_code=404, detail="no report generated yet")
    val = latest.read_text(encoding="utf-8").strip()
    if not _ASOF_RE.match(val) or not (_REPORTS_ROOT / val / "manifest.json").exists():
        raise HTTPException(status_code=404, detail="latest snapshot missing")
    return val


@router.get("/api/reports/correlation")
def get_manifest(
    as_of: str | None = Query(None, description="スナップショット識別子 (省略時は最新)"),
    _master: User = Depends(_require_master),
):
    """最新 (または指定) スナップショットの manifest を返す。"""
    resolved = _resolve_as_of(as_of)
    manifest_path = _REPORTS_ROOT / resolved / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    # 利用可能な過去スナップショット一覧も付与
    snaps = sorted(
        p.name for p in _REPORTS_ROOT.iterdir()
        if p.is_dir() and (p / "manifest.json").exists()
    )
    data["available_snapshots"] = snaps
    return data


@router.get("/api/reports/correlation/section/{section_id}", response_class=PlainTextResponse)
def get_section(
    section_id: str,
    as_of: str | None = Query(None),
    _master: User = Depends(_require_master),
):
    """セクションの Markdown 本文を text/plain で返す。"""
    if not _ID_RE.match(section_id):
        raise HTTPException(status_code=400, detail="invalid section id")
    resolved = _resolve_as_of(as_of)
    md_path = _REPORTS_ROOT / resolved / "sections" / f"{section_id}.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="section not found")
    return PlainTextResponse(md_path.read_text(encoding="utf-8"), media_type="text/markdown; charset=utf-8")


@router.get("/api/reports/correlation/download/{name}")
def download_csv(
    name: str,
    as_of: str | None = Query(None),
    _master: User = Depends(_require_master),
):
    """CSV (matrices/ または ルートの catalog.csv) をストリーム配信。"""
    if not _CSV_RE.match(name):
        raise HTTPException(status_code=400, detail="invalid file name")
    resolved = _resolve_as_of(as_of)
    base = _REPORTS_ROOT / resolved
    # catalog.csv はルート、その他は matrices/ 配下
    candidate = (base / name) if name == "catalog.csv" else (base / "matrices" / name)
    # パストラバーサル最終防御: 解決後パスが base 配下であること
    try:
        candidate.resolve().relative_to(base.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid path")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(candidate, media_type="text/csv", filename=name)
