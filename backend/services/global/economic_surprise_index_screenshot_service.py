"""
エコノミックサプライズ指数（Economic Surprise Index）画像配信サービス

手動配置されたPNG画像を配信する。
画像ファイルの更新日時が変わると自動的に新しい画像が配信される。

画像パス:
- global: backend/data/picture/エコノミックサプライズ指数（global）.png
- japan:  backend/data/picture/エコノミックサプライズ指数（japan）.png
- china:  backend/data/picture/エコノミックサプライズ指数（china）.png
"""
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from zoneinfo import ZoneInfo


JST = ZoneInfo("Asia/Tokyo")

# 画像ディレクトリ
PICTURE_DIR = Path(__file__).parent.parent.parent / "data" / "picture"

# 地域設定
REGION_CONFIG = {
    "global": {
        "image_filename": "エコノミックサプライズ指数（global）.png",
        "page_url": "https://en.macromicro.me/charts/45866/global-citi-surprise-index",
        "label": "Global",
    },
    "japan": {
        "image_filename": "エコノミックサプライズ指数（japan）.png",
        "page_url": "https://en.macromicro.me/charts/55983/japan-citi-surprise-index-earning",
        "label": "Japan",
    },
    "china": {
        "image_filename": "エコノミックサプライズ指数（china）.png",
        "page_url": "https://en.macromicro.me/charts/55758/cn-citi-surprise-index-earning",
        "label": "China",
    },
}

VALID_REGIONS = list(REGION_CONFIG.keys())


class EconomicSurpriseIndexScreenshotService:
    """Economic Surprise Index 画像配信サービス（手動更新方式）"""

    def __init__(self):
        pass

    def _image_path(self, region: str) -> Path:
        return PICTURE_DIR / REGION_CONFIG[region]["image_filename"]

    def _get_file_mtime(self, region: str) -> str | None:
        """画像ファイルの更新日時を取得"""
        path = self._image_path(region)
        if path.exists():
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=JST)
            return mtime.isoformat()
        return None

    def get_screenshot_url(self, region: str = "global") -> Dict[str, Any]:
        """画像URL情報を取得（ファイルの更新日時をlast_updatedとして返す）"""
        if region not in REGION_CONFIG:
            return {"screenshot_url": None, "last_updated": None}

        path = self._image_path(region)
        result: Dict[str, Any] = {
            "screenshot_url": None,
            "last_updated": None,
        }

        if path.exists():
            result["screenshot_url"] = f"/api/global/economic-surprise-index-screenshot/image?region={region}"
            result["last_updated"] = self._get_file_mtime(region)

        return result

    def get_all_screenshot_urls(self) -> Dict[str, Any]:
        """全地域の画像URL情報を取得"""
        result = {}
        for region in VALID_REGIONS:
            result[region] = self.get_screenshot_url(region)
        return result

    def get_cache_status(self, region: str = "global") -> Dict[str, Any]:
        """画像ステータスを取得"""
        if region not in REGION_CONFIG:
            return {"error": f"Unknown region: {region}"}

        path = self._image_path(region)
        return {
            "indicator": f"Economic Surprise Index ({region})",
            "source": "MacroMicro (手動更新)",
            "image_path": str(path),
            "image_exists": path.exists(),
            "last_updated": self._get_file_mtime(region),
        }

    def invalidate_cache(self, region: str = "global") -> bool:
        """互換性のため残す（手動更新方式では何もしない）"""
        return True

    def get_available_regions(self) -> List[str]:
        """利用可能な地域コードを返す"""
        return VALID_REGIONS


# シングルトンインスタンス
economic_surprise_index_screenshot_service = EconomicSurpriseIndexScreenshotService()
