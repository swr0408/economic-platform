"""
UK ONS PPIサービス
ONS PPIデータセットから生産者物価指数データを取得

指標:
- Producer output (factory gate) prices: 出荷価格
  - JVZ7: PPI Output All Manufacturing (Index 2015=100) → YoY/MoM計算
- Producer input prices: 投入価格
  - K646: PPI Input All Manufacturing (Index 2015=100) → YoY/MoM計算

データソース:
- ONS PPI Dataset (Producer Price Index)
- https://www.ons.gov.uk/economy/inflationandpriceindices/datasets/producerpriceindexstatisticalbulletindataset

発表スケジュール:
- 毎月中旬（CPIと同日・FMPカレンダー）

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
DATA_CACHE_FILE = CACHE_DIR / "ons_ppi_cache.json"


class ONSPPIService:
    """UK ONS PPIサービス"""

    DATA_CACHE_KEY = "uk:ons_ppi:data"
    ECONALPHA_ID = "ons_ppi"

    # ONS PPI Dataset URL
    ONS_PPI_URL = "https://www.ons.gov.uk/file?uri=/economy/inflationandpriceindices/datasets/producerpriceindexstatisticalbulletindataset/current/ppi.csv"

    # CDID codes for PPI series
    # Output (Factory Gate) prices
    # Input prices
    SERIES_CODES = {
        # Output prices (Factory Gate / 出荷価格)
        "FSR2": {"name": "PPI Output Manufactured Products", "type": "index", "category": "output"},
        # Input prices (投入価格)
        "GHIK": {"name": "PPI Input Materials", "type": "index", "category": "input_materials"},
        "GHIM": {"name": "PPI Input Fuels", "type": "index", "category": "input_fuels"},
    }

    # FMPカレンダー検索パターン
    FMP_EVENT_PATTERN = "PPI"

    def __init__(self):
        pass

    def get_ons_ppi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ONS PPIデータを取得"""
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
            # 最新値を決定（Output YoYから）
            output_yoy = api_result.get("series", {}).get("output_yoy", {}).get("data", [])
            latest = output_yoy[-1] if output_yoy else None

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
            print(f"[ONS PPI] Error getting next release: {e}")
            return None

    def _fetch_from_ons(self) -> Optional[Dict[str, Any]]:
        """ONSからPPIデータを取得"""
        try:
            print(f"[ONS PPI] Fetching data from PPI dataset")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(self.ONS_PPI_URL, headers=headers, timeout=120)
            response.raise_for_status()

            print(f"[ONS PPI] Successfully fetched PPI data: {len(response.text)} bytes")

            # CSVをパース
            return self._process_ons_csv(response.text)

        except Exception as e:
            print(f"[ONS PPI] Error fetching from ONS: {e}")
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
                    print(f"[ONS PPI] Found series {code} at column index {series_indices[code]}")
                except ValueError:
                    print(f"[ONS PPI] Series {code} not found in CSV")
                    continue

            if not series_indices:
                print("[ONS PPI] No series found in CSV")
                return None

            # メタデータ行をスキップ（ファイル構造によって調整）
            try:
                next(csv_reader)  # PreUnit row
            except StopIteration:
                pass

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
                            if value_str and value_str != '..':
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

            # PPI Output (FSR2) - Index → YoY/MoM計算
            if "FSR2" in series_data and series_data["FSR2"]:
                fsr2_data = sorted(series_data["FSR2"], key=lambda x: x["date"])

                # YoY計算
                yoy_data = self._calculate_yoy(fsr2_data)
                result_series["output_yoy"] = {
                    "data": yoy_data,
                    "metadata": {"code": "FSR2", "name": "PPI Output YoY"}
                }
                print(f"[ONS PPI] Processed {len(yoy_data)} PPI Output YoY data points")

                # MoM計算
                mom_data = self._calculate_mom(fsr2_data)
                result_series["output_mom"] = {
                    "data": mom_data,
                    "metadata": {"code": "FSR2", "name": "PPI Output MoM"}
                }
                print(f"[ONS PPI] Processed {len(mom_data)} PPI Output MoM data points")

            # PPI Input Materials (GHIK) - Index → YoY/MoM計算
            if "GHIK" in series_data and series_data["GHIK"]:
                ghik_data = sorted(series_data["GHIK"], key=lambda x: x["date"])

                # YoY計算
                yoy_data = self._calculate_yoy(ghik_data)
                result_series["input_yoy"] = {
                    "data": yoy_data,
                    "metadata": {"code": "GHIK", "name": "PPI Input Materials YoY"}
                }
                print(f"[ONS PPI] Processed {len(yoy_data)} PPI Input Materials YoY data points")

                # MoM計算
                mom_data = self._calculate_mom(ghik_data)
                result_series["input_mom"] = {
                    "data": mom_data,
                    "metadata": {"code": "GHIK", "name": "PPI Input Materials MoM"}
                }
                print(f"[ONS PPI] Processed {len(mom_data)} PPI Input Materials MoM data points")

            return {
                "series": result_series,
                "metadata": {
                    "source": "Office for National Statistics",
                    "dataset": "PPI Producer Price Index",
                    "description": "UK PPI Data (Output and Input prices)",
                },
            }

        except Exception as e:
            print(f"[ONS PPI] Error processing CSV: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _calculate_yoy(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """指数データから前年比を計算"""
        if len(data) < 13:
            return []

        yoy_data = []
        for i in range(12, len(data)):
            current = data[i]
            year_ago = data[i - 12]
            if current["value"] and year_ago["value"]:
                yoy = ((current["value"] - year_ago["value"]) / year_ago["value"]) * 100
                yoy_data.append({
                    "date": current["date"],
                    "value": round(yoy, 2)
                })

        return yoy_data

    def _calculate_mom(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """指数データから前月比を計算"""
        if len(data) < 2:
            return []

        mom_data = []
        for i in range(1, len(data)):
            current = data[i]
            previous = data[i - 1]
            if current["value"] and previous["value"]:
                mom = ((current["value"] - previous["value"]) / previous["value"]) * 100
                mom_data.append({
                    "date": current["date"],
                    "value": round(mom, 2)
                })

        return mom_data

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        return should_refresh_by_pattern(self.FMP_EVENT_PATTERN, last_updated_str, country="GB")

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ONS PPI] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ONS PPI] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        series_counts = {}
        if cached_data and cached_data.get("series"):
            for key, series in cached_data["series"].items():
                if series and series.get("data"):
                    series_counts[key] = len(series["data"])

        return {
            "indicator": "ONS PPI",
            "source": "ONS PPI Dataset",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "series_counts": series_counts,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ons_ppi_service = ONSPPIService()
