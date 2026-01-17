"""
BOE Service Base Class
BOEサービスの共通基底クラス

共通機能:
- Redis/ファイルキャッシュ管理
- キャッシュ更新判定
- フォールバックデータ
"""
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from zoneinfo import ZoneInfo

from core.redis_client import redis_client
from .boe_mpr_utils import DEFAULT_MPR_MONTHS

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")


class BOEServiceBase(ABC):
    """BOEサービスの共通基底クラス

    サブクラスで実装が必要なもの:
    - DATA_CACHE_KEY: Redisキャッシュキー
    - CACHE_FILE_PATH: ファイルキャッシュパス
    - DATA_KEY: レスポンスのメインデータキー
    - _fetch_data_from_source(): データソースからの取得処理
    """

    # サブクラスで定義
    DATA_CACHE_KEY: str = ""
    CACHE_FILE_PATH: Optional[Path] = None
    DATA_KEY: str = ""

    def fetch_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """データを取得（キャッシュ優先）

        Args:
            force_refresh: Trueの場合、キャッシュを無視して再取得

        Returns:
            データ辞書
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        self.DATA_KEY: cached_data.get(self.DATA_KEY, {}),
                        "metadata": cached_data.get("metadata", {}),
                        "cached": True,
                        "source": "redis",
                    }

        # データソースから取得
        data = self._fetch_data_from_source()

        if data:
            cache_payload = {
                self.DATA_KEY: data.get(self.DATA_KEY, {}),
                "metadata": data.get("metadata", {}),
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                self.DATA_KEY: data.get(self.DATA_KEY, {}),
                "metadata": data.get("metadata", {}),
                "cached": False,
                "source": "boe_mpr",
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                self.DATA_KEY: file_cache.get(self.DATA_KEY, {}),
                "metadata": file_cache.get("metadata", {}),
                "cached": True,
                "source": "file (fallback)",
            }

        return self._get_fallback_data()

    @abstractmethod
    def _fetch_data_from_source(self) -> Optional[Dict[str, Any]]:
        """データソースからデータを取得

        サブクラスで実装が必要

        Returns:
            データ辞書、失敗時はNone
        """
        pass

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定

        更新条件:
        - 前回更新から7日以上経過
        - MPR発表月の20:00-20:10（ロンドン時間）かつ60秒以上経過

        Args:
            last_updated_str: 前回更新日時（ISO形式）

        Returns:
            更新が必要な場合True
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)

            # 7日以上経過
            if (now - last_updated).total_seconds() >= 7 * 24 * 3600:
                return True

            # MPR発表タイミング（ロンドン時間20:00-20:10）
            now_london = now.astimezone(LONDON)
            if now_london.month in DEFAULT_MPR_MONTHS:
                if now_london.hour == 20 and now_london.minute <= 10:
                    if (now - last_updated).total_seconds() >= 60:
                        return True

            return False

        except Exception as e:
            logger.error(f"Error in should_refresh: {e}")
            return True

    def _get_fallback_data(self) -> Dict[str, Any]:
        """空のフォールバックデータを返す

        Returns:
            フォールバックデータ辞書
        """
        return {
            self.DATA_KEY: {},
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "source": "Bank of England",
                "error": f"Failed to fetch BOE {self.DATA_KEY} data"
            },
            "cached": False,
            "source": "none",
        }

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む

        Returns:
            キャッシュデータ、ない場合はNone
        """
        if self.CACHE_FILE_PATH is None:
            return None

        try:
            if not self.CACHE_FILE_PATH.exists():
                return None
            with open(self.CACHE_FILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存

        Args:
            data: 保存するデータ
        """
        if self.CACHE_FILE_PATH is None:
            return

        try:
            self.CACHE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(self.CACHE_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化

        Returns:
            成功した場合True
        """
        return redis_client.delete(self.DATA_CACHE_KEY)
