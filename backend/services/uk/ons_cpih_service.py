"""
UK ONS CPI/CPIHサービス
ONS MM23データセットからCPI/CPIHデータを取得

指標:
- D7BT: CPI All Items (Index 2015=100) → YoY計算
- DKC6: CPI Core (Index 2015=100) → YoY計算
- D7OE: CPI All Items MoM
- DKI7: CPI Core MoM
- L55O: CPIH All Items YoY
- L5LQ: CPIH Core YoY

データソース:
- ONS MM23 Dataset (Consumer Price Indices)
- https://www.ons.gov.uk/economy/inflationandpriceindices/datasets/consumerpriceindices

発表スケジュール:
- 毎月中旬（FMPカレンダー）

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

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ons_cpih_cache.json"


class ONSCPIHService:
    """UK ONS CPI/CPIHサービス"""

    DATA_CACHE_KEY = "uk:ons_cpih:data"
    ECONALPHA_ID = "ons_cpih"

    # ONS MM23 Dataset URL
    ONS_MM23_URL = "https://www.ons.gov.uk/file?uri=/economy/inflationandpriceindices/datasets/consumerpriceindices/current/mm23.csv"

    # CDID codes for CPI/CPIH series
    SERIES_CODES = {
        "D7BT": {"name": "CPI All Items", "type": "index", "category": "headline"},
        "DKC6": {"name": "CPI Core", "type": "index", "category": "core"},
        "D7OE": {"name": "CPI All Items MoM", "type": "mom", "category": "headline"},
        "DKI7": {"name": "CPI Core MoM", "type": "mom", "category": "core"},
        "L55O": {"name": "CPIH All Items YoY", "type": "yoy", "category": "cpih_headline"},
        "L5LQ": {"name": "CPIH Core YoY", "type": "yoy", "category": "cpih_core"},
        # CPI Components (YoY rates)
        "DKL5": {"name": "CPI Energy YoY", "type": "yoy", "category": "component"},
        "D7I7": {"name": "CPI Electricity YoY", "type": "yoy", "category": "component"},
        "D7G8": {"name": "CPI Food & Non-alcoholic YoY", "type": "yoy", "category": "component"},
        "D7NN": {"name": "CPI Services YoY", "type": "yoy", "category": "component"},
        "D7NM": {"name": "CPI Goods YoY", "type": "yoy", "category": "component"},
        "D7GQ": {"name": "CPI Rent YoY", "type": "yoy", "category": "component"},
    }

    # FMPカレンダー検索パターン
    FMP_EVENT_PATTERN = "CPI"

    def __init__(self):
        pass

    def get_ons_cpih_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ONS CPI/CPIHデータを取得"""
        # 次回発表日を取得
        next_release = self._get_next_release()

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "series": cached_data.get("series", {}),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ONSからデータを取得
        api_result = self._fetch_from_ons()

        if api_result:
            # 最新値を決定（CPI All Items YoYから）
            cpi_all_yoy = api_result.get("series", {}).get("cpi_all_yoy", {}).get("data", [])
            latest = cpi_all_yoy[-1] if cpi_all_yoy else None

            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )
            cache_payload = {
                "series": api_result.get("series", {}),
                "latest": latest,
                "metadata": api_result.get("metadata", {}),
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "series": api_result.get("series", {}),
                "latest": latest,
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
                "series": file_cache.get("series", {}),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "series": {},
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
            print(f"[ONS CPIH] Error getting next release: {e}")
            return None

    def _fetch_from_ons(self) -> Optional[Dict[str, Any]]:
        """ONSからCPI/CPIHデータを取得"""
        try:
            print(f"[ONS CPIH] Fetching data from MM23 dataset")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(self.ONS_MM23_URL, headers=headers, timeout=120)
            response.raise_for_status()

            print(f"[ONS CPIH] Successfully fetched MM23 data: {len(response.text)} bytes")

            # CSVをパース
            return self._process_ons_csv(response.text)

        except Exception as e:
            print(f"[ONS CPIH] Error fetching from ONS: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _process_ons_csv(self, csv_text: str) -> Optional[Dict[str, Any]]:
        """ONS CSVをパースして構造化データに変換"""
        try:
            csv_reader = csv.reader(StringIO(csv_text))

            # ヘッダー行を読み込む
            title_row = next(csv_reader)
            cdid_row = next(csv_reader)

            # 各系列のカラムインデックスを特定
            series_indices = {}
            for code in self.SERIES_CODES.keys():
                try:
                    series_indices[code] = cdid_row.index(code)
                except ValueError:
                    print(f"[ONS CPIH] Series {code} not found in CSV")
                    continue

            if not series_indices:
                print("[ONS CPIH] No series found in CSV")
                return None

            # メタデータ行をスキップ
            preunit_row = next(csv_reader)
            unit_row = next(csv_reader)
            release_date_row = next(csv_reader)
            next_release_row = next(csv_reader)
            important_notes_row = next(csv_reader)
            next(csv_reader)  # 空行

            # 月の略称
            valid_months = {'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                           'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'}
            month_to_num = {
                'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
            }

            # データを抽出
            series_data = {code: [] for code in series_indices.keys()}

            for row in csv_reader:
                if not row or not row[0]:
                    continue

                date_str = row[0].strip()
                parts = date_str.split()

                # 月次データのみ処理（年次・四半期をスキップ）
                if len(parts) != 2:
                    continue

                year_str = parts[0]
                month_str = parts[1].upper()

                if month_str not in valid_months:
                    continue

                try:
                    year = int(year_str)
                    if year < 2000:
                        continue

                    month = month_to_num[month_str]
                    iso_date = f"{year}-{month:02d}-01"

                    for code, idx in series_indices.items():
                        if len(row) > idx:
                            value_str = row[idx].strip()
                            if value_str:
                                try:
                                    value = float(value_str)
                                    series_data[code].append({
                                        "date": iso_date,
                                        "raw_date": date_str,
                                        "value": value,
                                        "year": year,
                                        "month": month,
                                    })
                                except ValueError:
                                    continue

                except (ValueError, IndexError):
                    continue

            # 各系列を処理
            result_series = {}

            # CPI All Items (D7BT) - Index → YoY計算
            if "D7BT" in series_data and series_data["D7BT"]:
                d7bt_data = sorted(series_data["D7BT"], key=lambda x: x["date"])
                yoy_data = self._calculate_yoy(d7bt_data)
                result_series["cpi_all_yoy"] = {
                    "data": yoy_data,
                    "metadata": {"code": "D7BT", "name": "CPI All Items YoY"}
                }
                print(f"[ONS CPIH] Processed {len(yoy_data)} CPI All Items YoY data points")

            # CPI Core (DKC6) - Index → YoY計算
            if "DKC6" in series_data and series_data["DKC6"]:
                dkc6_data = sorted(series_data["DKC6"], key=lambda x: x["date"])
                yoy_data = self._calculate_yoy(dkc6_data)
                result_series["cpi_core_yoy"] = {
                    "data": yoy_data,
                    "metadata": {"code": "DKC6", "name": "CPI Core YoY"}
                }
                print(f"[ONS CPIH] Processed {len(yoy_data)} CPI Core YoY data points")

            # CPI All Items MoM (D7OE) - そのまま使用
            if "D7OE" in series_data and series_data["D7OE"]:
                d7oe_data = sorted(series_data["D7OE"], key=lambda x: x["date"])
                mom_data = [{"date": d["date"], "value": round(d["value"], 2)} for d in d7oe_data]
                result_series["cpi_all_mom"] = {
                    "data": mom_data,
                    "metadata": {"code": "D7OE", "name": "CPI All Items MoM"}
                }
                print(f"[ONS CPIH] Processed {len(mom_data)} CPI All Items MoM data points")

            # CPI Core MoM (DKI7) - そのまま使用
            if "DKI7" in series_data and series_data["DKI7"]:
                dki7_data = sorted(series_data["DKI7"], key=lambda x: x["date"])
                mom_data = [{"date": d["date"], "value": round(d["value"], 2)} for d in dki7_data]
                result_series["cpi_core_mom"] = {
                    "data": mom_data,
                    "metadata": {"code": "DKI7", "name": "CPI Core MoM"}
                }
                print(f"[ONS CPIH] Processed {len(mom_data)} CPI Core MoM data points")

            # CPIH All Items YoY (L55O) - そのまま使用
            if "L55O" in series_data and series_data["L55O"]:
                l55o_data = sorted(series_data["L55O"], key=lambda x: x["date"])
                yoy_data = [{"date": d["date"], "value": round(d["value"], 2)} for d in l55o_data]
                result_series["cpih_all_yoy"] = {
                    "data": yoy_data,
                    "metadata": {"code": "L55O", "name": "CPIH All Items YoY"}
                }
                print(f"[ONS CPIH] Processed {len(yoy_data)} CPIH All Items YoY data points")

            # CPIH Core YoY (L5LQ) - そのまま使用
            if "L5LQ" in series_data and series_data["L5LQ"]:
                l5lq_data = sorted(series_data["L5LQ"], key=lambda x: x["date"])
                yoy_data = [{"date": d["date"], "value": round(d["value"], 2)} for d in l5lq_data]
                result_series["cpih_core_yoy"] = {
                    "data": yoy_data,
                    "metadata": {"code": "L5LQ", "name": "CPIH Core YoY"}
                }
                print(f"[ONS CPIH] Processed {len(yoy_data)} CPIH Core YoY data points")

            # CPI Components (YoY rates) - そのまま使用
            component_codes = {
                "DKL5": "energy_yoy",
                "D7I7": "electricity_yoy",
                "D7G8": "food_yoy",
                "D7NN": "services_yoy",
                "D7NM": "goods_yoy",
                "D7GQ": "rent_yoy",
            }
            for code, key in component_codes.items():
                if code in series_data and series_data[code]:
                    sorted_data = sorted(series_data[code], key=lambda x: x["date"])
                    yoy_data = [{"date": d["date"], "value": round(d["value"], 2)} for d in sorted_data]
                    result_series[key] = {
                        "data": yoy_data,
                        "metadata": {"code": code, "name": self.SERIES_CODES[code]["name"]}
                    }
                    print(f"[ONS CPIH] Processed {len(yoy_data)} {key} data points")

            return {
                "series": result_series,
                "metadata": {
                    "source": "Office for National Statistics",
                    "dataset": "MM23 Consumer Price Indices",
                    "description": "UK CPI/CPIH Data",
                },
            }

        except Exception as e:
            print(f"[ONS CPIH] Error processing CSV: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _calculate_yoy(self, index_data: List[Dict]) -> List[Dict]:
        """インデックスデータから前年比を計算"""
        result = []
        lookback = 12  # 12ヶ月前

        for i in range(lookback, len(index_data)):
            current = index_data[i]
            prev = index_data[i - lookback]

            # YoY計算
            yoy = ((current["value"] - prev["value"]) / prev["value"]) * 100
            result.append({
                "date": current["date"],
                "value": round(yoy, 2),
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
                if should_refresh_by_pattern(self.FMP_EVENT_PATTERN, last_updated_str, country="GB"):
                    print(f"[ONS CPIH] FMP pattern indicates refresh needed")
                    return True
            except Exception as e:
                print(f"[ONS CPIH] Error checking FMP refresh: {e}")

            return False

        except Exception as e:
            print(f"[ONS CPIH] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ONS CPIH] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ONS CPIH] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        series_counts = {}
        if cached_data:
            series = cached_data.get("series", {})
            for key, value in series.items():
                series_counts[key] = len(value.get("data", []))

        return {
            "indicator": "ONS CPI/CPIH",
            "source": "Office for National Statistics",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "series_counts": series_counts,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ons_cpih_service = ONSCPIHService()
