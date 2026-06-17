"""
Truflation US CPI Inflation Index スクリーンショットAPIルーター

静的なPNG画像（1Y / 3Y / Max）を配信する。

エンドポイント:
- GET /api/usa/truflation-screenshot - メタデータ（スクリーンショット一覧）
- GET /api/usa/truflation-screenshot/truflation_1y - 1Y画像
- GET /api/usa/truflation-screenshot/truflation_3y - 3Y画像
- GET /api/usa/truflation-screenshot/truflation_max - Max画像
"""
import os
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
def get_screenshot_metadata():
    """Truflationスクリーンショットのメタデータを取得

    各画像のファイルmtimeを `version` として返す。フロントはこれを
    キャッシュバスティング用クエリ(`?v=`)に使うことで、画像を差し替えた
    ときだけブラウザキャッシュが無効化される（普段はキャッシュが効く）。
    """
    screenshots = []
    for item in SCREENSHOT_KEYS:
        path = IMAGE_DIR / item["filename"]
        exists = path.exists()
        version = int(os.path.getmtime(path)) if exists else 0
        screenshots.append({
            "key": item["key"],
            "label": item["label"],
            "url": f"/api/usa/truflation-screenshot/{item['key']}",
            "exists": exists,
            "version": version,
        })
    return {"screenshots": screenshots}


def _image_response(filename: str) -> FileResponse | dict:
    """PNGを返す。差し替え検知のため再検証必須のキャッシュ制御を付与。"""
    path = IMAGE_DIR / filename
    if path.exists():
        return FileResponse(
            path,
            media_type="image/png",
            filename=filename,
            # 同一URL(?v=未変更)でも必ずETag/Last-Modifiedで再検証させる。
            # 差し替え後は version クエリが変わるため確実に新画像を取得できる。
            headers={"Cache-Control": "no-cache, must-revalidate"},
        )
    return {"error": "Screenshot not available"}


@router.get("/truflation_1y")
def get_truflation_1y():
    """Truflation 1Y画像を取得"""
    return _image_response("truflation_1y.png")


@router.get("/truflation_3y")
def get_truflation_3y():
    """Truflation 3Y画像を取得"""
    return _image_response("truflation_3y.png")


@router.get("/truflation_max")
def get_truflation_max():
    """Truflation Max画像を取得"""
    return _image_response("truflation_max.png")
