"""
エコノミックサプライズ指数 画像配信APIルーター

手動配置されたPNG画像を配信。ファイルの更新日時でキャッシュバスティング。

エンドポイント:
- GET /api/global/economic-surprise-index-screenshot - 画像URL情報（?region=global|japan|china）
- GET /api/global/economic-surprise-index-screenshot/image - 画像ファイル（?region=global|japan|china）
- GET /api/global/economic-surprise-index-screenshot/cache/status - ステータス
"""
import importlib as _importlib

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse

try:
    _mod = _importlib.import_module("backend.services.global.economic_surprise_index_screenshot_service")
except ImportError:
    _mod = _importlib.import_module("services.global.economic_surprise_index_screenshot_service")
economic_surprise_index_screenshot_service = _mod.economic_surprise_index_screenshot_service
REGION_CONFIG = _mod.REGION_CONFIG
PICTURE_DIR = _mod.PICTURE_DIR


router = APIRouter(
    prefix="/api/global/economic-surprise-index-screenshot",
    tags=["global", "economic-surprise-index-screenshot"]
)


@router.get("")
async def get_screenshot_url(
    region: str = Query("global", description="地域 (global, japan, china)"),
):
    """画像URL情報を取得"""
    urls = economic_surprise_index_screenshot_service.get_screenshot_url(region=region)
    return {
        "screenshot_url": urls["screenshot_url"],
        "last_updated": urls["last_updated"],
        "region": region,
        "refreshed": False,
    }


@router.get("/image")
async def get_screenshot_image(
    region: str = Query("global", description="地域 (global, japan, china)"),
):
    """画像ファイルを取得。ファイルの更新日時をETagとして返す。"""
    if region not in REGION_CONFIG:
        raise HTTPException(status_code=400, detail=f"Unknown region: {region}")

    config = REGION_CONFIG[region]
    image_path = PICTURE_DIR / config["image_filename"]

    if not image_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"画像ファイルが見つかりません: {config['image_filename']}",
        )

    # ファイルの更新日時をETagに使用（更新されたらブラウザキャッシュが無効化される）
    mtime = int(image_path.stat().st_mtime)
    return FileResponse(
        image_path,
        media_type="image/png",
        filename=f"economic_surprise_index_{region}.png",
        headers={"ETag": f'"{region}-{mtime}"'},
    )


@router.get("/cache/status")
async def get_cache_status(
    region: str = Query("global", description="地域 (global, japan, china)"),
):
    """画像ステータスを取得"""
    return economic_surprise_index_screenshot_service.get_cache_status(region=region)
