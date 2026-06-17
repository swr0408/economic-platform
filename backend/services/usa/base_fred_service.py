"""
FRED APIサービス基底クラス

FRED APIを使用する全サービスの共通処理を提供:
- Redis/ファイルキャッシュ管理
- FMPスケジュールベースのキャッシュ更新判定
- 前月比・前年比の計算

継承時に設定が必要:
- SERIES_ID: FREDシリーズID
- DATA_CACHE_KEY: Redisキャッシュキー
- DATA_CACHE_FILE: ファイルキャッシュパス
- ECONALPHA_ID: FMPマッピング用指標ID
"""
import os
import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests

from core.redis_client import redis_client
from services.usa.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")


class BaseFREDService(ABC):
    """
    FRED APIサービスの基底クラス

    主な機能:
    - キャッシュ管理（Redis + ファイル）
    - 発表日時ベースのキャッシュ更新判定
    - 前月比・前年比の計算
    """

    BASE_URL = "https://api.stlouisfed.org/fred"

    # サブクラスで設定必須
    SERIES_ID: str = ""
    DATA_CACHE_KEY: str = ""
    DATA_CACHE_FILE: Optional[Path] = None
    ECONALPHA_ID: str = ""  # FMPマッピング用ID

    # デフォルトの開始日
    DEFAULT_START_DATE: str = "2000-01-01"

    def __init__(self):
        self.api_key = os.environ.get("FRED_API_KEY", "")

    # ==========================================================================
    # 公開メソッド
    # ==========================================================================

    def get_data(
        self,
        start_date: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        データを取得（キャッシュ優先）

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [...],
                "latest": {...},
                "next_release": {...} | None,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str, cached_data):
                    return self._build_response(
                        data=cached_data.get("data", []),
                        latest=cached_data.get("latest"),
                        cached=True,
                        source="redis",
                        last_updated=last_updated_str
                    )

        # ファイルキャッシュチェック
        if not force_refresh and self.DATA_CACHE_FILE:
            file_cache = self._load_file_cache(self.DATA_CACHE_FILE)
            if file_cache:
                last_updated_str = file_cache.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str, file_cache):
                    # Redisにも保存
                    redis_client.set(self.DATA_CACHE_KEY, file_cache, expire=0)
                    return self._build_response(
                        data=file_cache.get("data", []),
                        latest=file_cache.get("latest"),
                        cached=True,
                        source="file",
                        last_updated=last_updated_str
                    )

        # 外部APIから取得
        api_data = self._fetch_from_api(start_date)

        if api_data:
            latest = api_data[-1] if api_data else None
            now_str = datetime.now(JST).isoformat()

            # FRED が更新遅延で古いデータを返した場合、last_updated を進めない。
            # 発表当日にソース未反映のまま force_refresh されると、last_updated が
            # 発表時刻より後になり staleness 判定が「更新済み」と誤認 → FRED が後から
            # 反映しても再取得されず取りこぼす。データより新しくない取得では last_updated
            # を維持し、反映まで再取得を続けさせる（fred_utils.FREDDataService と同方針）。
            existing_cache = redis_client.get(self.DATA_CACHE_KEY)
            existing_latest_date = None
            if existing_cache and existing_cache.get("latest"):
                existing_latest_date = existing_cache["latest"].get("date")
            new_latest_date = latest.get("date") if latest else None

            if existing_latest_date and new_latest_date and new_latest_date <= existing_latest_date:
                # データ自体は更新（既存値の改定がありうる）が last_updated は維持
                last_updated_val = existing_cache.get("last_updated", now_str)
                print(f"  {self.__class__.__name__}: FRED data not newer "
                      f"(latest={new_latest_date}), keeping last_updated={last_updated_val}")
            else:
                last_updated_val = now_str

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "latest_data_date": latest["date"] if latest else None,
                "last_updated": last_updated_val
            }

            # キャッシュに保存
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            if self.DATA_CACHE_FILE:
                self._save_file_cache(self.DATA_CACHE_FILE, cache_payload)

            return self._build_response(
                data=api_data,
                latest=latest,
                cached=False,
                source="api",
                last_updated=last_updated_val
            )

        # 取得失敗時はファイルキャッシュから返す
        if self.DATA_CACHE_FILE:
            file_cache = self._load_file_cache(self.DATA_CACHE_FILE)
            if file_cache:
                return self._build_response(
                    data=file_cache.get("data", []),
                    latest=file_cache.get("latest"),
                    cached=True,
                    source="file (fallback)",
                    last_updated=file_cache.get("last_updated")
                )

        return self._build_response(
            data=[],
            latest=None,
            cached=False,
            source="none",
            last_updated=None,
            error="No data available"
        )

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "series_id": self.SERIES_ID,
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID) if self.ECONALPHA_ID else None,
            "file_cache_exists": self.DATA_CACHE_FILE.exists() if self.DATA_CACHE_FILE else False
        }

    # ==========================================================================
    # 内部メソッド - サブクラスでオーバーライド可能
    # ==========================================================================

    def _fetch_from_api(self, start_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        FRED APIからデータを取得

        サブクラスでカスタマイズが必要な場合はオーバーライド
        """
        try:
            if not self.api_key:
                print("FRED_API_KEY not set")
                return []

            print(f"Fetching {self.SERIES_ID} from FRED...")

            if not start_date:
                start_date = self.DEFAULT_START_DATE

            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": self.SERIES_ID,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "asc"
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            raw_data = self._parse_observations(data.get("observations", []))
            result = self._calculate_changes(raw_data)

            print(f"Fetched {len(result)} records from FRED ({self.SERIES_ID})")
            return result

        except Exception as e:
            print(f"Error fetching {self.SERIES_ID}: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_observations(self, observations: List[Dict]) -> List[Dict[str, Any]]:
        """
        APIレスポンスをパース

        サブクラスでカスタマイズが必要な場合はオーバーライド
        """
        raw_data = []
        for obs in observations:
            if obs.get("value") and obs["value"] != ".":
                try:
                    raw_data.append({
                        "date": obs["date"],
                        "value": round(float(obs["value"]), 2)
                    })
                except (ValueError, TypeError):
                    continue
        return raw_data

    def _calculate_changes(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        前月比・前年比を計算

        サブクラスでカスタマイズが必要な場合はオーバーライド
        """
        result = []
        for i, item in enumerate(raw_data):
            entry = {
                "date": item["date"],
                "value": item["value"],
                "mom": None,
                "yoy": None
            }

            # 前月比
            if i >= 1:
                prev_value = raw_data[i - 1]["value"]
                if prev_value and prev_value != 0:
                    entry["mom"] = round(((item["value"] - prev_value) / prev_value) * 100, 2)

            # 前年比
            if i >= 12:
                year_ago_value = raw_data[i - 12]["value"]
                if year_ago_value and year_ago_value != 0:
                    entry["yoy"] = round(((item["value"] - year_ago_value) / year_ago_value) * 100, 2)

            result.append(entry)

        return result

    def _should_refresh(self, last_updated_str: str, cached_data: Dict[str, Any]) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        FMPスケジュールベースの3分方式で判定
        """
        if self.ECONALPHA_ID:
            return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)
        return False

    # ==========================================================================
    # 内部ユーティリティ
    # ==========================================================================

    def _build_response(
        self,
        data: List[Dict[str, Any]],
        latest: Optional[Dict[str, Any]],
        cached: bool,
        source: str,
        last_updated: Optional[str],
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """レスポンスを構築"""
        response = {
            "data": data,
            "latest": latest,
            "next_release": None,
            "cached": cached,
            "source": source,
            "last_updated": last_updated
        }
        if error:
            response["error"] = error
        return response

    def _load_file_cache(self, cache_file: Path) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not cache_file.exists():
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, cache_file: Path, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {cache_file}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")
