"""
ONS GVA（月間GDP）サービス
Office for National StatisticsからGross Value Added（総付加価値）データを取得

指標:
- ED3H: GVA Monthly (3m on 3m growth) CVM SA - 対前3か月成長率
- ECY2: GVA Monthly (Index) CVM SA - 月次指数

データソース:
- ONS Time Series Data
- https://www.ons.gov.uk/economy/grossdomesticproductgdp

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
DATA_CACHE_FILE = CACHE_DIR / "ons_gva_cache.json"


class ONSGVAService:
    """ONS GVA（月間GDP）サービス"""

    DATA_CACHE_KEY = "uk:ons_gva:data"
    ECONALPHA_ID = "ons_gva"

    # ONS Time Series API URLs
    ED3H_CSV_URL = "https://www.ons.gov.uk/generator?format=csv&uri=/economy/grossdomesticproductgdp/timeseries/ed3h/mgdp"
    ECY2_CSV_URL = "https://www.ons.gov.uk/generator?format=csv&uri=/economy/grossdomesticproductgdp/timeseries/ecy2/mgdp"

    # FMPカレンダー検索パターン（indicator_event_mappingで定義）
    FMP_EVENT_PATTERNS = ["Gross Domestic Product MoM", "Gross Domestic Product YoY", "GDP 3-Month Avg"]

    def __init__(self):
        pass

    def get_ons_gva_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ONS GVAデータを取得"""
        # 次回発表日を取得
        next_release = self._get_next_release()

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "ed3h": cached_data.get("ed3h", {}),
                        "ecy2": cached_data.get("ecy2", {}),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ONSからデータを取得
        api_result = self._fetch_from_ons()

        if api_result:
            cache_payload = {
                "ed3h": api_result.get("ed3h", {}),
                "ecy2": api_result.get("ecy2", {}),
                "metadata": api_result.get("metadata", {}),
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "ed3h": api_result.get("ed3h", {}),
                "ecy2": api_result.get("ecy2", {}),
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
                "ed3h": file_cache.get("ed3h", {}),
                "ecy2": file_cache.get("ecy2", {}),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "ed3h": {},
            "ecy2": {},
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
            print(f"[ONS GVA] Error getting next release: {e}")
            return None

    def _fetch_from_ons(self) -> Optional[Dict[str, Any]]:
        """ONSから全データを取得"""
        try:
            print("[ONS GVA] Fetching data from ONS")

            ed3h_data = self._parse_csv_data(self.ED3H_CSV_URL, "ED3H")
            ecy2_data = self._parse_csv_data(self.ECY2_CSV_URL, "ECY2")

            if not ed3h_data or not ecy2_data:
                print("[ONS GVA] Failed to fetch one or more series")
                return None

            # ECY2のYoYとMoMを計算
            ecy2_yoy = self._calculate_yoy_change(ecy2_data["data"])
            ecy2_mom = self._calculate_mom_change(ecy2_data["data"])

            # ECY2の3か月移動平均のYoY変化率を計算（3か月前年比）
            ecy2_3m_yoy = self._calculate_3m_avg_yoy(ecy2_data["data"])

            return {
                "ed3h": {
                    "data": ed3h_data["data"],
                    "metadata": ed3h_data["metadata"],
                },
                "ecy2": {
                    "3m_yoy": ecy2_3m_yoy,
                    "data": ecy2_data["data"],
                    "yoy": ecy2_yoy,
                    "mom": ecy2_mom,
                    "metadata": ecy2_data["metadata"],
                },
                "metadata": {
                    "source": "Office for National Statistics",
                    "description": "月間GDP（GVA）",
                    "ed3h_title": ed3h_data["metadata"].get("title", ""),
                    "ecy2_title": ecy2_data["metadata"].get("title", ""),
                },
            }

        except Exception as e:
            print(f"[ONS GVA] Error fetching from ONS: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_csv_data(self, url: str, series_name: str) -> Optional[Dict[str, Any]]:
        """ONS CSVデータをパース"""
        try:
            print(f"[ONS GVA] Fetching {series_name} from {url}")

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

            print(f"[ONS GVA] Extracted {len(monthly_data_points)} monthly data points for {series_name}")

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
            print(f"[ONS GVA] Error parsing {series_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _calculate_yoy_change(self, data_points: List[Dict]) -> List[Dict]:
        """前年同期比（YoY）の変化率を計算"""
        yoy_data = []
        sorted_data = sorted(data_points, key=lambda x: x["date"])

        for i, point in enumerate(sorted_data):
            if i >= 12:  # 12か月前が必要
                prev_point = sorted_data[i - 12]
                current_value = point["value"]
                prev_value = prev_point["value"]

                if prev_value and prev_value != 0:
                    yoy_change = ((current_value - prev_value) / prev_value) * 100
                    yoy_data.append({
                        "date": point["date"],
                        "period": point["period"],
                        "value": current_value,
                        "yoy_change": round(yoy_change, 2),
                    })

        return yoy_data

    def _calculate_mom_change(self, data_points: List[Dict]) -> List[Dict]:
        """前月比（MoM）の変化率を計算"""
        mom_data = []
        sorted_data = sorted(data_points, key=lambda x: x["date"])

        for i in range(1, len(sorted_data)):
            current_point = sorted_data[i]
            prev_point = sorted_data[i - 1]

            current_value = current_point["value"]
            prev_value = prev_point["value"]

            if prev_value and prev_value != 0:
                mom_change = ((current_value - prev_value) / prev_value) * 100
                mom_data.append({
                    "date": current_point["date"],
                    "period": current_point["period"],
                    "value": current_value,
                    "mom_change": round(mom_change, 2),
                })

        return mom_data

    def _calculate_3m_avg_yoy(self, data_points: List[Dict]) -> List[Dict]:
        """3か月移動平均の前年同期比（3M YoY）を計算

        ECY2インデックスの3か月移動平均を計算し、その前年同期比を算出。
        これが「3か月前年比」の正しい計算方法。
        """
        result = []
        sorted_data = sorted(data_points, key=lambda x: x["date"])

        # 3か月移動平均を計算
        avg_data = []
        for i in range(2, len(sorted_data)):
            # 当月と過去2か月の平均
            values = [sorted_data[j]["value"] for j in range(i - 2, i + 1)]
            avg_value = sum(values) / 3
            avg_data.append({
                "date": sorted_data[i]["date"],
                "period": sorted_data[i]["period"],
                "avg_value": avg_value,
            })

        # 3か月移動平均の前年同期比を計算
        for i, point in enumerate(avg_data):
            if i >= 12:  # 12か月前が必要
                prev_point = avg_data[i - 12]
                current_avg = point["avg_value"]
                prev_avg = prev_point["avg_value"]

                if prev_avg and prev_avg != 0:
                    yoy_change = ((current_avg - prev_avg) / prev_avg) * 100
                    result.append({
                        "date": point["date"],
                        "period": point["period"],
                        "value": round(current_avg, 2),
                        "yoy_change": round(yoy_change, 2),
                    })

        return result

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
                from services.uk.fmp_next_release_utils import should_refresh_by_pattern
                for pattern in self.FMP_EVENT_PATTERNS:
                    if should_refresh_by_pattern(pattern, last_updated_str, country="GB"):
                        print(f"[ONS GVA] FMP pattern '{pattern}' indicates refresh needed")
                        return True
            except Exception as e:
                print(f"[ONS GVA] Error checking FMP refresh: {e}")

            return False

        except Exception as e:
            print(f"[ONS GVA] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ONS GVA] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ONS GVA] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ONS GVA (Monthly GDP)",
            "source": "Office for National Statistics",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "ed3h_count": len(cached_data.get("ed3h", {}).get("data", [])) if cached_data else 0,
            "ecy2_count": len(cached_data.get("ecy2", {}).get("data", [])) if cached_data else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ons_gva_service = ONSGVAService()
