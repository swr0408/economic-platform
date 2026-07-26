"""
ONS Production Industries（鉱工業生産）サービス
Office for National Statisticsから鉱工業生産データを取得

指標:
- ED2T: Production Industries - Total (YoY growth) CVM SA - 前年比成長率
- ECYZ: Production Industries - Total (MoM growth) CVM SA - 前月比成長率

データソース:
- ONS Time Series Data
- https://www.ons.gov.uk/economy/economicoutputandproductivity/output/timeseries

発表スケジュール:
- 不定期（FMPカレンダーから取得）
- 発表時刻: 15:00-16:00 ロンドン時間

キャッシュ方式: Redis + ファイルキャッシュ（FMP発表日時ベース判定）
"""
import csv
import json
import requests
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ons_production_cache.json"


class ONSProductionService:
    """ONS Production Industries（鉱工業生産）サービス"""

    DATA_CACHE_KEY = "uk:ons_production:data"
    ECONALPHA_ID = "ons_production"

    # ONS Time Series API URLs
    ED2T_CSV_URL = "https://www.ons.gov.uk/generator?format=csv&uri=/economy/grossdomesticproductgdp/timeseries/ed2t/mgdp"
    ECYZ_CSV_URL = "https://www.ons.gov.uk/generator?format=csv&uri=/economy/grossdomesticproductgdp/timeseries/ecyz/mgdp"

    # FMPカレンダー検索パターン（indicator_event_mappingで定義）
    FMP_EVENT_PATTERNS = ["Industrial Production MoM", "Industrial Production YoY"]

    def __init__(self):
        pass

    def get_ons_production_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ONS Production Industriesデータを取得"""
        # 次回発表日を取得
        next_release = self._get_next_release()

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "ed2t": cached_data.get("ed2t", {}),
                        "ecyz": cached_data.get("ecyz", {}),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ONSからデータを取得
        api_result = self._fetch_from_ons()

        if api_result:
            from services.usa.fmp_next_release_utils import guarded_last_updated_keys, _max_date_of
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated_keys(
                self.DATA_CACHE_KEY, ("ed2t", "ecyz"),
                _max_date_of(api_result.get("ed2t", {}).get("data", []), api_result.get("ecyz", {}).get("data", [])), now_str
            )
            cache_payload = {
                "ed2t": api_result.get("ed2t", {}),
                "ecyz": api_result.get("ecyz", {}),
                "metadata": api_result.get("metadata", {}),
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "ed2t": api_result.get("ed2t", {}),
                "ecyz": api_result.get("ecyz", {}),
                "metadata": api_result.get("metadata", {}),
                "next_release": next_release,
                "cached": False,
                "source": "ons_api",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "ed2t": file_cache.get("ed2t", {}),
                "ecyz": file_cache.get("ecyz", {}),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "ed2t": {},
            "ecyz": {},
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
            from services.uk.fmp_next_release_utils import get_next_release_by_pattern

            # 複数のパターンで検索し、最も近いものを返す
            candidates = []
            for pattern in self.FMP_EVENT_PATTERNS:
                result = get_next_release_by_pattern(pattern, country="GB")
                if result:
                    candidates.append(result)

            if candidates:
                candidates.sort(key=lambda x: x.get("date", ""))
                return candidates[0]

            return None
        except Exception as e:
            print(f"[ONS Production] Error getting next release: {e}")
            return None

    def _fetch_from_ons(self) -> Optional[Dict[str, Any]]:
        """ONSから全データを取得"""
        try:
            print("[ONS Production] Fetching data from ONS")

            ed2t_data = self._parse_csv_data(self.ED2T_CSV_URL, "ED2T")
            ecyz_data = self._parse_csv_data(self.ECYZ_CSV_URL, "ECYZ")

            if not ed2t_data or not ecyz_data:
                print("[ONS Production] Failed to fetch one or more series")
                return None

            return {
                "ed2t": {
                    "data": ed2t_data["data"],
                    "metadata": ed2t_data["metadata"],
                },
                "ecyz": {
                    "data": ecyz_data["data"],
                    "metadata": ecyz_data["metadata"],
                },
                "metadata": {
                    "source": "Office for National Statistics",
                    "description": "鉱工業生産（Production Industries）",
                    "ed2t_title": ed2t_data["metadata"].get("title", ""),
                    "ecyz_title": ecyz_data["metadata"].get("title", ""),
                },
            }

        except Exception as e:
            print(f"[ONS Production] Error fetching from ONS: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_csv_data(self, url: str, series_name: str) -> Optional[Dict[str, Any]]:
        """ONS CSVデータをパース"""
        try:
            print(f"[ONS Production] Fetching {series_name} from {url}")

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
            unit = unit_row[1] if len(unit_row) > 1 else ""
            release_date = release_date_row[1] if len(release_date_row) > 1 else ""
            next_release = next_release_row[1] if len(next_release_row) > 1 else ""

            monthly_data_points = []

            for row in csv_reader:
                if len(row) >= 2 and row[0] and row[1]:
                    try:
                        period_str = row[0].strip()
                        value = float(row[1].strip())

                        # 月次データのみ処理（形式: "YYYY MMM"）
                        if " " in period_str and len(period_str.split()) == 2:
                            try:
                                date_obj = datetime.strptime(period_str, "%Y %b")
                                date_str = date_obj.strftime("%Y-%m-01")

                                monthly_data_points.append({
                                    "date": date_str,
                                    "value": round(value, 2),
                                    "period": period_str,
                                })
                            except ValueError:
                                continue
                    except (ValueError, IndexError):
                        continue

            print(f"[ONS Production] Extracted {len(monthly_data_points)} monthly data points for {series_name}")

            return {
                "data": monthly_data_points,
                "metadata": {
                    "title": title,
                    "cdid": cdid,
                    "unit": unit,
                    "release_date": release_date,
                    "next_release_ons": next_release,
                },
            }

        except Exception as e:
            print(f"[ONS Production] Error parsing {series_name}: {e}")
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

            # 24時間以上経過していれば更新
            # FMPカレンダーがUK月次発表イベント(GDP/IP)を落とすと発表日駆動のrefreshが
            # 空振りし、集約が旧月で凍結する(2026-07-16 ONS 5月分で発生)。
            # 集約層の MAX_CACHE_AGE_HOURS(24h) と揃え、発表当日中に自己回復させる。
            if hours_since_update >= 24:
                return True

            # FMPパターンベースの更新判定
            try:
                from services.uk.fmp_next_release_utils import should_refresh_by_pattern
                for pattern in self.FMP_EVENT_PATTERNS:
                    if should_refresh_by_pattern(pattern, last_updated_str, country="GB"):
                        print(f"[ONS Production] FMP pattern '{pattern}' indicates refresh needed")
                        return True
            except Exception as e:
                print(f"[ONS Production] Error checking FMP refresh: {e}")

            return False

        except Exception as e:
            print(f"[ONS Production] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ONS Production] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ONS Production] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ONS Production Industries",
            "source": "Office for National Statistics",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "ed2t_count": len(cached_data.get("ed2t", {}).get("data", [])) if cached_data else 0,
            "ecyz_count": len(cached_data.get("ecyz", {}).get("data", [])) if cached_data else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ons_production_service = ONSProductionService()
