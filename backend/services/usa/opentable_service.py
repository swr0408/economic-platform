"""
OpenTable Seated Diners サービス
OpenTableからレストラン予約件数前年比チャートを提供

データソース: 手動配置画像（backend/data/manual_update/daily/the_restaurant_industry/）
  - change_in_seated_diners_by_week_*.png  (週次チャート)
  - change_in_seated_diners_by_month_*.png (月次テーブル)

更新方法: 手動でスクリーンショットを配置
キャッシュ方式: ファイル更新日時ベース
"""
import logging
import re
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, List, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# 手動配置画像ディレクトリ
MANUAL_DIR = Path(__file__).parent.parent.parent / "data" / "manual_update" / "daily" / "the_restaurant_industry"

# 静的配信ベースURL
STATIC_BASE = "/static/manual_update/daily/the_restaurant_industry"


class OpenTableService:
    """OpenTable Seated Diners サービス（手動画像配置方式）"""

    CACHE_KEY = "usa:opentable:screenshot"

    def get_opentable_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        OpenTableチャートデータを取得

        Returns:
            {
                "image_url": str | None,       # 後方互換（週次チャート）
                "images": [...],               # タブ切替用の全画像リスト
                "latest": {"date": str, "description": str},
                "last_updated": str,
                "cached": bool,
                "source": str
            }
        """
        images = self._scan_images()

        if not images:
            return {
                "image_url": None,
                "images": [],
                "latest": None,
                "last_updated": None,
                "cached": False,
                "source": "none",
                "error": "No images available",
            }

        # 最新ファイルの更新日時
        latest_mtime = max(
            datetime.fromtimestamp(
                (MANUAL_DIR / img["filename"]).stat().st_mtime, tz=JST
            )
            for img in images
        )

        # 後方互換: 週次チャートを image_url に
        week_image = next((img for img in images if "week" in img["filename"]), None)
        primary_url = week_image["url"] if week_image else images[0]["url"]

        return {
            "image_url": primary_url,
            "images": [{"label": img["label"], "url": img["url"]} for img in images],
            "latest": self._get_latest_info(images),
            "last_updated": latest_mtime.isoformat(),
            "cached": False,
            "source": "manual",
        }

    def _scan_images(self) -> List[Dict[str, Any]]:
        """ディレクトリ内の画像をスキャンしてラベル付きリストを返す"""
        if not MANUAL_DIR.exists():
            return []

        images = []
        for f in sorted(MANUAL_DIR.iterdir(), key=lambda p: self._sort_key(p.name)):
            if not f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                continue

            label = self._filename_to_label(f.name)
            images.append({
                "filename": f.name,
                "url": f"{STATIC_BASE}/{f.name}",
                "label": label,
            })

        return images

    def _sort_key(self, filename: str) -> int:
        """週次を先、月次を後にソート"""
        name = filename.lower()
        if "by_week" in name:
            return 0
        if "by_month" in name:
            return 1
        return 2

    def _filename_to_label(self, filename: str) -> str:
        """ファイル名からタブ表示用ラベルを生成"""
        name = Path(filename).stem.lower()

        if "by_week" in name:
            return "週次 (Weekly)"
        if "by_month" in name:
            return "月次 (Monthly)"

        # フォールバック: ファイル名をクリーンアップ
        label = name.replace("_", " ").replace("change in seated diners", "").strip()
        return label or filename

    def _get_latest_info(self, images: List[Dict[str, Any]]) -> Dict[str, Any]:
        """画像ファイルから最新データ情報を推定"""
        # ファイル名から年を抽出してdescriptionを生成
        for img in images:
            match = re.search(r"(\d{4})vs(\d{4})", img["filename"])
            if match:
                return {
                    "date": date.today().isoformat(),
                    "description": f"{match.group(1)} vs. {match.group(2)}",
                }

        # ファイルの最終更新日時をフォールバック
        latest_file = max(
            (MANUAL_DIR / img["filename"] for img in images),
            key=lambda p: p.stat().st_mtime,
        )
        mtime = datetime.fromtimestamp(latest_file.stat().st_mtime, tz=JST)
        return {
            "date": mtime.strftime("%Y-%m-%d"),
            "description": f"Data as of {mtime.strftime('%b %d, %Y')}",
        }

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化（手動方式ではnoop）"""
        from core.redis_client import redis_client
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        images = self._scan_images()
        return {
            "manual_dir": str(MANUAL_DIR),
            "dir_exists": MANUAL_DIR.exists(),
            "image_count": len(images),
            "images": [img["filename"] for img in images],
        }


# シングルトンインスタンス
opentable_service = OpenTableService()
