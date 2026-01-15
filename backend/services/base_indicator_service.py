"""
経済指標サービス基底クラス

全ての経済指標サービスの共通処理を提供する抽象基底クラス。

機能:
- 2段階キャッシュ（Redis → ファイル）
- フォールバック処理
- キャッシュステータス管理
- 発表スケジュールベースの更新判定

使用方法:
    from services.base_indicator_service import BaseIndicatorService

    class MyIndicatorService(BaseIndicatorService):
        DATA_CACHE_KEY = "my:indicator:data"
        CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "my"
        DATA_CACHE_FILE = CACHE_DIR / "my_indicator_cache.json"

        def _fetch_from_source(self) -> Optional[Dict[str, Any]]:
            # データソースから取得する実装
            pass

        def _should_refresh(self, last_updated_str: str) -> bool:
            # 更新判定の実装
            pass

        def _calculate_next_release(self) -> Optional[Dict[str, Any]]:
            # 次回発表日計算の実装
            pass
"""
import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

JST = ZoneInfo("Asia/Tokyo")


class BaseIndicatorService(ABC):
    """
    経済指標サービス基底クラス

    サブクラスで以下を定義:
    - DATA_CACHE_KEY: Redisキャッシュキー
    - CACHE_DIR: ファイルキャッシュディレクトリ
    - DATA_CACHE_FILE: ファイルキャッシュパス
    - _fetch_from_source(): データソースからの取得
    - _should_refresh(): 更新判定
    - _calculate_next_release(): 次回発表日計算
    """

    # サブクラスで定義するクラス属性
    DATA_CACHE_KEY: str = ""
    CACHE_DIR: Path = Path(".")
    DATA_CACHE_FILE: Path = Path(".")

    # データソース名（ログ・ステータス用）
    SOURCE_NAME: str = "unknown"
    INDICATOR_NAME: str = "Unknown Indicator"
    SOURCE_URL: str = ""

    def __init__(self):
        # キャッシュディレクトリを作成
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        データを取得（キャッシュ優先）

        取得順序:
        1. Redisキャッシュ
        2. ファイルキャッシュ
        3. データソースから新規取得
        4. ファイルキャッシュ（フォールバック）

        Args:
            force_refresh: True の場合、キャッシュを無視してソースから取得

        Returns:
            データ辞書（data, latest, next_release, cached, source, last_updated）
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    cached_data["cached"] = True
                    cached_data["source"] = "redis"
                    cached_data["next_release"] = self._calculate_next_release()
                    return cached_data

        # ファイルキャッシュチェック
        if not force_refresh:
            file_cache = self._load_file_cache()
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    file_cache["cached"] = True
                    file_cache["source"] = "file"
                    file_cache["next_release"] = self._calculate_next_release()
                    return file_cache

        # データソースから取得
        result = self._fetch_from_source()
        if result and result.get("data"):
            latest = self._get_latest(result["data"])
            next_release = self._calculate_next_release()

            cache_payload = {
                "data": result["data"],
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": result["data"],
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": self.SOURCE_NAME,
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            file_cache["cached"] = True
            file_cache["source"] = "file (fallback)"
            file_cache["next_release"] = self._calculate_next_release()
            return file_cache

        return {
            "data": [],
            "latest": None,
            "next_release": self._calculate_next_release(),
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _get_latest(self, data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """最新データを取得"""
        if not data:
            return None
        return data[-1]

    @abstractmethod
    def _fetch_from_source(self) -> Optional[Dict[str, Any]]:
        """
        データソースからデータを取得

        Returns:
            {"data": [...]} 形式の辞書。失敗時はNone
        """
        pass

    @abstractmethod
    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        Args:
            last_updated_str: 最終更新日時のISO文字列

        Returns:
            True: 更新が必要
            False: キャッシュ有効
        """
        pass

    @abstractmethod
    def _calculate_next_release(self) -> Optional[Dict[str, Any]]:
        """
        次回発表予定日を計算

        Returns:
            {"date": "YYYY-MM-DD", "datetime_jst": "...", "label": "..."} 形式
        """
        pass

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not self.DATA_CACHE_FILE.exists():
                return None
            with open(self.DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": self.INDICATOR_NAME,
            "source": self.SOURCE_NAME,
            "url": self.SOURCE_URL,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._calculate_next_release(),
            "file_cache_exists": self.DATA_CACHE_FILE.exists(),
        }


class ScheduleBasedIndicatorService(BaseIndicatorService):
    """
    スケジュールチェッカーベースの経済指標サービス

    release_schedule_utils のチェッカーを使用して更新判定を行う。
    """

    # サブクラスで設定するスケジュールチェッカー
    _schedule_checker: Any = None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """スケジュールチェッカーを使用して更新判定"""
        if self._schedule_checker is None:
            # チェッカーが未設定の場合はフォールバック
            return self._should_refresh_fallback(last_updated_str)

        return self._schedule_checker.should_refresh(last_updated_str)

    def _should_refresh_fallback(self, last_updated_str: str) -> bool:
        """
        フォールバック更新判定（7日以上経過で更新）

        スケジュールチェッカーが利用できない場合のデフォルト動作
        """
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            return (now - last_updated).days >= 7

        except Exception:
            return True

    def _calculate_next_release(self) -> Optional[Dict[str, Any]]:
        """スケジュールチェッカーから次回発表日を取得"""
        if self._schedule_checker is None:
            return None

        try:
            status = self._schedule_checker.get_status()
            next_release_str = status.get("next_release")
            if next_release_str:
                next_release_dt = datetime.fromisoformat(next_release_str)
                return {
                    "date": next_release_dt.strftime("%Y-%m-%d"),
                    "datetime_jst": next_release_str,
                    "label": f"{self.INDICATOR_NAME} - {next_release_dt.strftime('%Y/%m/%d %H:%M')} JST",
                }
        except Exception as e:
            print(f"Error calculating next release: {e}")

        return None
