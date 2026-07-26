"""
ONS Public Sector Net Borrowing Ex Banks サービス
Office for National Statisticsからイギリスの公的部門純借入データを取得

指標:
- HF6X: Public sector net borrowing excluding public sector banks (PSNB ex)
- CPOA: Central government net borrowing
- DZLS: Public sector net debt excluding public sector banks (PSND ex)
- KSE6: Public sector net debt as % of GDP

データソース:
- ONS Time Series Data
- https://www.ons.gov.uk/economy/governmentpublicsectorandtaxes/publicsectorfinance/timeseries/hf6x/pusf

発表スケジュール:
- 月次（通常、翌月下旬）
- FMPカレンダーから次回発表日を取得

キャッシュ方式: FMP発表日時ベース判定方式
"""
import csv
import json
import time
import requests
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client
from services.uk.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ons_public_sector_net_borrowing_cache.json"


class ONSPublicSectorNetBorrowingService:
    """ONS Public Sector Net Borrowing サービス"""

    DATA_CACHE_KEY = "uk:public_sector_net_borrowing:data"
    ECONALPHA_ID = "uk_public_sector_net_borrowing_ex_bank"
    FMP_COUNTRY = "GB"
    FMP_EVENT_PATTERN = "Public Sector Net Borrowing"

    # ONS Time Series API URLs
    # HF6X: Public sector net borrowing excluding public sector banks (£m)
    PSNB_EX_URL = "https://www.ons.gov.uk/generator?format=csv&uri=/economy/governmentpublicsectorandtaxes/publicsectorfinance/timeseries/hf6x/pusf"
    # CPOA: Central government net borrowing (£m)
    CGNB_URL = "https://www.ons.gov.uk/generator?format=csv&uri=/economy/governmentpublicsectorandtaxes/publicsectorfinance/timeseries/cpoa/pusf"
    # DZLS: Public sector net debt excluding public sector banks (£m)
    PSND_EX_URL = "https://www.ons.gov.uk/generator?format=csv&uri=/economy/governmentpublicsectorandtaxes/publicsectorfinance/timeseries/dzls/pusf"
    # KSE6: Public sector net debt as % of GDP
    PSND_GDP_URL = "https://www.ons.gov.uk/generator?format=csv&uri=/economy/governmentpublicsectorandtaxes/publicsectorfinance/timeseries/kse6/pusf"

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Public Sector Net Borrowingデータを取得"""
        # 次回発表日を取得
        next_release = self._get_next_release()

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "psnb_ex": cached_data.get("psnb_ex", []),
                        "cgnb": cached_data.get("cgnb", []),
                        "psnd_ex": cached_data.get("psnd_ex", []),
                        "psnd_gdp": cached_data.get("psnd_gdp", []),
                        "latest_psnb_ex": cached_data.get("latest_psnb_ex"),
                        "latest_cgnb": cached_data.get("latest_cgnb"),
                        "latest_psnd_ex": cached_data.get("latest_psnd_ex"),
                        "latest_psnd_gdp": cached_data.get("latest_psnd_gdp"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ONSからデータを取得
        api_result = self._fetch_all_series()

        if api_result:
            latest_psnb_ex = api_result["psnb_ex"][-1] if api_result["psnb_ex"] else None
            latest_cgnb = api_result["cgnb"][-1] if api_result["cgnb"] else None
            latest_psnd_ex = api_result["psnd_ex"][-1] if api_result["psnd_ex"] else None
            latest_psnd_gdp = api_result["psnd_gdp"][-1] if api_result["psnd_gdp"] else None

            from services.usa.fmp_next_release_utils import guarded_last_updated_keys, _max_date_of
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated_keys(
                self.DATA_CACHE_KEY, ("psnb_ex", "cgnb", "psnd_ex", "psnd_gdp"),
                _max_date_of(api_result["psnb_ex"], api_result["cgnb"], api_result["psnd_ex"], api_result["psnd_gdp"]), now_str
            )
            cache_payload = {
                "psnb_ex": api_result["psnb_ex"],
                "cgnb": api_result["cgnb"],
                "psnd_ex": api_result["psnd_ex"],
                "psnd_gdp": api_result["psnd_gdp"],
                "latest_psnb_ex": latest_psnb_ex,
                "latest_cgnb": latest_cgnb,
                "latest_psnd_ex": latest_psnd_ex,
                "latest_psnd_gdp": latest_psnd_gdp,
                "metadata": {
                    "source": "Office for National Statistics",
                    "description": "イギリス公的部門純借入（銀行除く）",
                    "unit_borrowing": "£ million",
                    "unit_debt_gdp": "%",
                    "frequency": "Monthly",
                },
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "psnb_ex": api_result["psnb_ex"],
                "cgnb": api_result["cgnb"],
                "psnd_ex": api_result["psnd_ex"],
                "psnd_gdp": api_result["psnd_gdp"],
                "latest_psnb_ex": latest_psnb_ex,
                "latest_cgnb": latest_cgnb,
                "latest_psnd_ex": latest_psnd_ex,
                "latest_psnd_gdp": latest_psnd_gdp,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "ons_api",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "psnb_ex": file_cache.get("psnb_ex", []),
                "cgnb": file_cache.get("cgnb", []),
                "psnd_ex": file_cache.get("psnd_ex", []),
                "psnd_gdp": file_cache.get("psnd_gdp", []),
                "latest_psnb_ex": file_cache.get("latest_psnb_ex"),
                "latest_cgnb": file_cache.get("latest_cgnb"),
                "latest_psnd_ex": file_cache.get("latest_psnd_ex"),
                "latest_psnd_gdp": file_cache.get("latest_psnd_gdp"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "psnb_ex": [],
            "cgnb": [],
            "psnd_ex": [],
            "psnd_gdp": [],
            "latest_psnb_ex": None,
            "latest_cgnb": None,
            "latest_psnd_ex": None,
            "latest_psnd_gdp": None,
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
            return get_next_release_by_pattern(
                self.FMP_EVENT_PATTERN,
                country=self.FMP_COUNTRY
            )
        except Exception as e:
            print(f"[PSNB] Error getting next release: {e}")
            return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日時ベース）"""
        return should_refresh_by_pattern(
            self.FMP_EVENT_PATTERN,
            last_updated_str,
            country=self.FMP_COUNTRY
        )

    SERIES_KEYS = ("psnb_ex", "cgnb", "psnd_ex", "psnd_gdp")

    def _fetch_all_series(self) -> Optional[Dict[str, List[Dict]]]:
        """全シリーズのデータを取得

        ONSへ連続アクセスすると後続が一過性に失敗することがあるため、
        系列間に小休止を挟む。さらに空で返った系列は直近キャッシュで補完し、
        部分フェッチで全履歴を空に上書きする劣化を防ぐ（劣化上書きガード）。
        """
        try:
            result = {key: [] for key in self.SERIES_KEYS}

            series_specs = [
                ("psnb_ex", self.PSNB_EX_URL, "PSNB Ex"),
                ("cgnb", self.CGNB_URL, "CGNB"),
                ("psnd_ex", self.PSND_EX_URL, "PSND Ex"),
                ("psnd_gdp", self.PSND_GDP_URL, "PSND/GDP"),
            ]

            for idx, (key, url, name) in enumerate(series_specs):
                if idx > 0:
                    # ONSへの連続バーストを避ける
                    time.sleep(1.0)
                data = self._fetch_ons_csv(url, name)
                if data:
                    result[key] = data

            # 劣化上書きガード: 空で返った系列は直近キャッシュを再利用
            if not all(result[key] for key in self.SERIES_KEYS):
                prior = self._load_prior_cache()
                if prior:
                    for key in self.SERIES_KEYS:
                        if not result[key] and prior.get(key):
                            result[key] = prior[key]
                            print(
                                f"[PSNB] {key}: fetch empty -> reuse prior cache "
                                f"({len(prior[key])} points)"
                            )

            if any(result[key] for key in self.SERIES_KEYS):
                return result

            return None

        except Exception as e:
            print(f"[PSNB] Error fetching all series: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _load_prior_cache(self) -> Optional[Dict[str, Any]]:
        """直近の有効なキャッシュ（Redis優先、無ければファイル）を取得"""
        try:
            cached = redis_client.get(self.DATA_CACHE_KEY)
            if cached and any(cached.get(key) for key in self.SERIES_KEYS):
                return cached
        except Exception as e:
            print(f"[PSNB] Failed to load redis prior cache: {e}")
        return self._load_file_cache()

    def _fetch_ons_csv(self, url: str, series_name: str) -> List[Dict[str, Any]]:
        """ONSからCSVデータを取得してパース（一過性失敗に備えてリトライ）"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        for attempt in range(3):
            try:
                print(f"[PSNB] Fetching {series_name} from ONS... (attempt {attempt + 1})")
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()

                parsed = self._parse_monthly_csv(response.text, series_name)
                if parsed:
                    return parsed
                print(f"[PSNB] {series_name}: parsed 0 points, retrying...")
            except requests.exceptions.RequestException as e:
                print(f"[PSNB] Request error for {series_name} (attempt {attempt + 1}): {e}")
            except Exception as e:
                print(f"[PSNB] Error fetching {series_name} (attempt {attempt + 1}): {e}")

            if attempt < 2:
                time.sleep(2.0 * (attempt + 1))

        return []

    def _parse_monthly_csv(self, csv_text: str, series_name: str) -> List[Dict[str, Any]]:
        """ONS CSVデータをパース（月次データ）"""
        try:
            csv_reader = csv.reader(StringIO(csv_text))

            # ヘッダー行をスキップ（通常8行）
            for _ in range(8):
                try:
                    next(csv_reader)
                except StopIteration:
                    break

            data_points = []
            month_map = {
                'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
            }

            for row in csv_reader:
                if len(row) >= 2 and row[0] and row[1]:
                    try:
                        period_str = row[0].strip().upper()
                        value_str = row[1].strip()

                        # 空値やヘッダーをスキップ
                        if not value_str or value_str.lower() in ['value', '']:
                            continue

                        value = float(value_str)

                        # 月次データを処理 (形式: "YYYY MMM" e.g., "2024 NOV")
                        parts = period_str.split()
                        if len(parts) == 2:
                            year_str, month_str = parts
                            if year_str.isdigit() and month_str in month_map:
                                year = int(year_str)
                                month = month_map[month_str]

                                date_obj = datetime(year, month, 1)
                                date_str = date_obj.strftime("%Y-%m-01")

                                data_points.append({
                                    "date": date_str,
                                    "value": round(value, 2),
                                    "period": period_str,
                                })

                    except (ValueError, IndexError):
                        continue

            # 日付順にソート
            data_points.sort(key=lambda x: x["date"])
            print(f"[PSNB] Extracted {len(data_points)} {series_name} data points")
            return data_points

        except Exception as e:
            print(f"[PSNB] Error parsing {series_name} CSV: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[PSNB] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[PSNB] Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"[PSNB] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "UK Public Sector Net Borrowing Ex Banks",
            "source": "Office for National Statistics",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "psnb_ex_count": len(cached_data.get("psnb_ex", [])) if cached_data else 0,
            "psnd_gdp_count": len(cached_data.get("psnd_gdp", [])) if cached_data else 0,
            "latest_psnb_ex": cached_data.get("latest_psnb_ex") if cached_data else None,
            "next_release": get_next_release_by_pattern(
                self.FMP_EVENT_PATTERN,
                country=self.FMP_COUNTRY
            ),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ons_public_sector_net_borrowing_service = ONSPublicSectorNetBorrowingService()
