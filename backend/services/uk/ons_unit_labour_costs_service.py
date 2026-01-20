"""
UK ONS単位労働コストサービス
ONS Time Series APIから単位労働コストデータを取得

指標:
- DMWN: Unit labour costs (YoY % change) - 単位労働コスト前年比
- DMWO: Unit labour costs (QoQ % change) - 単位労働コスト前期比

データソース:
- ONS Time Series Data
- https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/labourproductivity

発表スケジュール:
- FMPカレンダーから自動取得（Labour Productivity QoQパターン）
- 四半期発表（労働生産性と同日）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import csv
import json
import requests
from datetime import datetime
from io import StringIO
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.uk.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ons_unit_labour_costs_cache.json"


class ONSUnitLabourCostsService:
    """UK ONS単位労働コストサービス"""

    DATA_CACHE_KEY = "uk:ons_unit_labour_costs:data"
    ECONALPHA_ID = "ons_unit_labour_costs"

    # ONS Time Series API URLs
    # DMWN: Unit labour costs (YoY % change)
    DMWN_CSV_URL = "https://www.ons.gov.uk/generator?format=csv&uri=/employmentandlabourmarket/peopleinwork/labourproductivity/timeseries/dmwn/ucst"
    # DMWO: Unit labour costs (QoQ % change)
    DMWO_CSV_URL = "https://www.ons.gov.uk/generator?format=csv&uri=/employmentandlabourmarket/peopleinwork/labourproductivity/timeseries/dmwo/ucst"

    # FMPカレンダー検索パターン（労働生産性と同じ）
    FMP_EVENT_PATTERN = "Labour Productivity QoQ"

    def __init__(self):
        pass

    def get_ons_unit_labour_costs_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ONS単位労働コストデータを取得"""
        # 次回発表日を取得
        next_release = self._get_next_release()

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "yoy": cached_data.get("yoy", {}),
                        "qoq": cached_data.get("qoq", {}),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ONSからデータを取得
        api_result = self._fetch_all_from_ons()

        if api_result:
            # 最新値を決定（YoYデータから）
            yoy_data = api_result.get("yoy", {}).get("data", [])
            latest = yoy_data[-1] if yoy_data else None

            cache_payload = {
                "yoy": api_result.get("yoy", {}),
                "qoq": api_result.get("qoq", {}),
                "latest": latest,
                "metadata": api_result.get("metadata", {}),
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "yoy": api_result.get("yoy", {}),
                "qoq": api_result.get("qoq", {}),
                "latest": latest,
                "metadata": api_result.get("metadata", {}),
                "next_release": next_release,
                "cached": False,
                "source": "ons_api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "yoy": file_cache.get("yoy", {}),
                "qoq": file_cache.get("qoq", {}),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "yoy": {},
            "qoq": {},
            "latest": None,
            "metadata": {},
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _get_next_release(self) -> Optional[Dict[str, Any]]:
        """次回発表日を取得 - FMPカレンダーから検索"""
        try:
            return get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country="GB")
        except Exception as e:
            print(f"[ONS Unit Labour Costs] Error getting next release: {e}")
            return None

    def _fetch_csv_data(self, url: str, series_name: str) -> Optional[Dict[str, Any]]:
        """単一のCSVデータソースをパース"""
        try:
            print(f"[ONS Unit Labour Costs] Fetching {series_name} from {url}")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            csv_reader = csv.reader(StringIO(response.text))

            # ヘッダー行を読み込む
            title_row = next(csv_reader)
            cdid_row = next(csv_reader)
            source_row = next(csv_reader)
            preunit_row = next(csv_reader)
            unit_row = next(csv_reader)
            release_date_row = next(csv_reader)
            next_release_row = next(csv_reader)
            notes_row = next(csv_reader)

            title = title_row[1] if len(title_row) > 1 else series_name
            cdid = cdid_row[1] if len(cdid_row) > 1 else ""
            unit = unit_row[1] if len(unit_row) > 1 else "%"
            release_date = release_date_row[1] if len(release_date_row) > 1 else ""
            next_release_ons = next_release_row[1] if len(next_release_row) > 1 else ""

            # 四半期データを読み込む（形式: "YYYY QN"）
            data_points = []

            for row in csv_reader:
                if len(row) >= 2 and row[0] and row[1]:
                    try:
                        period_str = row[0].strip()
                        value = float(row[1].strip())

                        # 四半期データのみ処理（形式: "YYYY QN"）
                        if " Q" in period_str:
                            # "YYYY QN" 形式をパース（例: "2024 Q1"）
                            year_str, quarter_str = period_str.split(" Q")
                            year = int(year_str)
                            quarter = int(quarter_str)

                            # 四半期の最初の月に変換
                            month = (quarter - 1) * 3 + 1
                            date_str = f"{year}-{month:02d}-01"

                            data_points.append({
                                "date": date_str,
                                "value": round(value, 2),
                                "period": period_str,
                            })
                    except (ValueError, IndexError):
                        continue

            print(f"[ONS Unit Labour Costs] Extracted {len(data_points)} data points for {series_name}")

            return {
                "data": data_points,
                "metadata": {
                    "title": title,
                    "cdid": cdid,
                    "unit": unit,
                    "release_date": release_date,
                    "next_release_ons": next_release_ons,
                },
            }

        except Exception as e:
            print(f"[ONS Unit Labour Costs] Error fetching {series_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_all_from_ons(self) -> Optional[Dict[str, Any]]:
        """ONSから全単位労働コストデータを取得"""
        try:
            # DMWN（YoY）を取得
            dmwn_data = self._fetch_csv_data(self.DMWN_CSV_URL, "Unit Labour Costs YoY (DMWN)")
            # DMWO（QoQ）を取得
            dmwo_data = self._fetch_csv_data(self.DMWO_CSV_URL, "Unit Labour Costs QoQ (DMWO)")

            if not dmwn_data or not dmwo_data:
                print("[ONS Unit Labour Costs] Failed to fetch one or more series")
                return None

            return {
                "yoy": {
                    "data": dmwn_data["data"],
                    "metadata": dmwn_data["metadata"],
                },
                "qoq": {
                    "data": dmwo_data["data"],
                    "metadata": dmwo_data["metadata"],
                },
                "metadata": {
                    "source": "Office for National Statistics",
                    "description": "単位労働コスト",
                    "series": {
                        "dmwn": "単位労働コスト前年比 (YoY %)",
                        "dmwo": "単位労働コスト前期比 (QoQ %)",
                    },
                },
            }

        except Exception as e:
            print(f"[ONS Unit Labour Costs] Error fetching from ONS: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=JST)

            now = datetime.now(JST)
            hours_since_update = (now - last_updated).total_seconds() / 3600

            # 7日以上経過していれば更新
            if hours_since_update >= 24 * 7:
                return True

            # FMPパターンベースの更新判定
            try:
                if should_refresh_by_pattern(self.FMP_EVENT_PATTERN, last_updated_str, country="GB"):
                    print(f"[ONS Unit Labour Costs] FMP pattern indicates refresh needed")
                    return True
            except Exception as e:
                print(f"[ONS Unit Labour Costs] Error checking FMP refresh: {e}")

            return False

        except Exception as e:
            print(f"[ONS Unit Labour Costs] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ONS Unit Labour Costs] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ONS Unit Labour Costs] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ONS Unit Labour Costs",
            "source": "Office for National Statistics",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "yoy_count": len(cached_data.get("yoy", {}).get("data", [])) if cached_data else 0,
            "qoq_count": len(cached_data.get("qoq", {}).get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ons_unit_labour_costs_service = ONSUnitLabourCostsService()
