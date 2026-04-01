"""
Truflation US CPI Inflation Index スクリーンショットAPIルーター

静的なPNG画像（1Y / 3Y / Max）を配信する。

エンドポイント:
- GET /api/usa/truflation-screenshot - メタデータ（スクリーンショット一覧）
- GET /api/usa/truflation-screenshot/truflation_1y - 1Y画像
- GET /api/usa/truflation-screenshot/truflation_3y - 3Y画像
- GET /api/usa/truflation-screenshot/truflation_max - Max画像
"""
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(
    prefix="/api/usa/truflation-screenshot",
    tags=["usa", "truflation"],
)

IMAGE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "manual_update" / "daily" / "truflation"

SCREENSHOT_KEYS = [
    {"key": "truflation_1y", "label": "1Y", "filename": "truflation_1y.png"},
    {"key": "truflation_3y", "label": "3Y", "filename": "truflation_3y.png"},
    {"key": "truflation_max", "label": "Max", "filename": "truflation_max.png"},
]


@router.get("")
async def get_screenshot_metadata():
    """Truflationスクリーンショットのメタデータを取得"""
    screenshots = []
    for item in SCREENSHOT_KEYS:
        path = IMAGE_DIR / item["filename"]
        screenshots.append({
            "key": item["key"],
            "label": item["label"],
            "url": f"/api/usa/truflation-screenshot/{item['key']}",
            "exists": path.exists(),
        })
    return {"screenshots": screenshots}


@router.get("/truflation_1y")
async def get_truflation_1y():
    """Truflation 1Y画像を取得"""
    path = IMAGE_DIR / "truflation_1y.png"
    if path.exists():
        return FileResponse(path, media_type="image/png", filename="truflation_1y.png")
    return {"error": "Screenshot not available"}


@router.get("/truflation_3y")
async def get_truflation_3y():
    """Truflation 3Y画像を取得"""
    path = IMAGE_DIR / "truflation_3y.png"
    if path.exists():
        return FileResponse(path, media_type="image/png", filename="truflation_3y.png")
    return {"error": "Screenshot not available"}


@router.get("/truflation_max")
async def get_truflation_max():
    """Truflation Max画像を取得"""
    path = IMAGE_DIR / "truflation_max.png"
    if path.exists():
        return FileResponse(path, media_type="image/png", filename="truflation_max.png")
    return {"error": "Screenshot not available"}
