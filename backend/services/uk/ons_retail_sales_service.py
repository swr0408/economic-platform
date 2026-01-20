"""
ONS小売売上高サービス
Office for National Statisticsから小売売上高データを取得

指標（全てVolume Seasonally Adjusted）:
- All Retail Inc Fuel YoY: 全小売（燃料込み）前年比
- All Retail Inc Fuel MoM: 全小売（燃料込み）前月比
- All Retail Ex Fuel YoY (Core): コア（燃料除く）前年比
- All Retail Ex Fuel MoM (Core): コア（燃料除く）前月比

データソース:
- ONS DRSI Dataset (直接ダウンロード)
- https://www.ons.gov.uk/businessindustryandtrade/retailindustry/datasets/retailsales

発表スケジュール:
- 毎月（通常月中旬）
- 発表時刻: 07:00 ロンドン時間

キャッシュ方式: Redis + ファイルキャッシュ（FMP発表日時ベース判定方式）
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
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "consumer"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ons_retail_sales_cache.json"


class ONSRetailSalesService:
    """ONS小売売上高サービス"""

    DATA_CACHE_KEY = "uk:ons_retail_sales:data"
    ECONALPHA_ID = "ons_retail_sales"

    # ONS DRSI Dataset URL（フルデータセット）
    DRSI_CSV_URL = "https://www.ons.gov.uk/file?uri=/businessindustryandtrade/retailindustry/datasets/retailsales/current/drsi.csv"

    # 系列タイトル（CSVヘッダーで検索）
    SERIES_TITLES = {
        # All Retail Inc Fuel (VOL SA)
        "inc_fuel_yoy": "RSI:All retail inc fuel:All Business:VOL SA:% change on same month a year ago",
        "inc_fuel_mom": "RSI:Month on prev month % change:All Business All retail inc fuel VOL SA",
        # All Retail Ex Fuel / Core (VOL SA)
        "ex_fuel_yoy": "RSI:All retail ex fuel:All Business:VOL SA:% change on same month a year ago",
        "ex_fuel_mom": "RSI:Month on prev month % change:All Business All retail ex fuel VOL SA",
    }

    # FMPカレンダー検索パターン
    FMP_EVENT_PATTERNS = ["Retail Sales MoM", "Retail Sales YoY"]

    def __init__(self):
        pass

    def get_ons_retail_sales_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ONS小売売上高データを取得（MoM/YoY + Core MoM/YoY）"""
        # 次回発表日を取得
        next_release = self._get_next_release()

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "mom": cached_data.get("mom", []),
                        "yoy": cached_data.get("yoy", []),
                        "core_mom": cached_data.get("core_mom", []),
                        "core_yoy": cached_data.get("core_yoy", []),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # ONSからデータを取得
        data = self._fetch_from_ons()

        if data:
            metadata = {
                "source": "Office for National Statistics",
                "dataset": "Retail Sales Index (DRSI)",
                "series": {
                    "yoy": "All retail inc fuel: VOL SA: % change on same month a year ago",
                    "mom": "All retail inc fuel: VOL SA: Month on prev month % change",
                    "core_yoy": "All retail ex fuel: VOL SA: % change on same month a year ago",
                    "core_mom": "All retail ex fuel: VOL SA: Month on prev month % change",
                },
                "description": "イギリス小売売上高（数量ベース・季節調整済み）",
            }

            cache_payload = {
                "mom": data.get("inc_fuel_mom", []),
                "yoy": data.get("inc_fuel_yoy", []),
                "core_mom": data.get("ex_fuel_mom", []),
                "core_yoy": data.get("ex_fuel_yoy", []),
                "metadata": metadata,
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "mom": data.get("inc_fuel_mom", []),
                "yoy": data.get("inc_fuel_yoy", []),
                "core_mom": data.get("ex_fuel_mom", []),
                "core_yoy": data.get("ex_fuel_yoy", []),
                "metadata": metadata,
                "next_release": next_release,
                "cached": False,
                "source": "ons_api",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "mom": file_cache.get("mom", []),
                "yoy": file_cache.get("yoy", []),
                "core_mom": file_cache.get("core_mom", []),
                "core_yoy": file_cache.get("core_yoy", []),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "mom": [],
            "yoy": [],
            "core_mom": [],
            "core_yoy": [],
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

            result = get_next_release_by_pattern(
                self.FMP_EVENT_PATTERNS[0],
                country="GB"
            )
            return result
        except Exception as e:
            print(f"[ONS Retail Sales] Error getting next release: {e}")
            return None

    def _fetch_from_ons(self) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """ONSからDRSIデータセットを取得してパース"""
        try:
            print(f"[ONS Retail Sales] Fetching DRSI dataset from ONS")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(self.DRSI_CSV_URL, headers=headers, timeout=60)
            response.raise_for_status()

            print(f"[ONS Retail Sales] Received {len(response.content)} bytes")

            return self._parse_drsi_csv(response.text)

        except requests.exceptions.RequestException as e:
            print(f"[ONS Retail Sales] Request error: {e}")
            return None
        except Exception as e:
            print(f"[ONS Retail Sales] Error fetching from ONS: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_drsi_csv(self, csv_text: str) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """ONS DRSI CSVデータをパース"""
        try:
            csv_reader = csv.reader(StringIO(csv_text))

            # ヘッダー行（タイトル行）を読み込む
            title_row = next(csv_reader)
            cdid_row = next(csv_reader)

            # 必要な列のインデックスを特定
            column_indices = {}
            for key, search_title in self.SERIES_TITLES.items():
                for i, title in enumerate(title_row):
                    # 完全一致または部分一致で検索
                    if title.strip('"') == search_title or search_title in title:
                        column_indices[key] = i
                        print(f"[ONS Retail Sales] Found '{key}' at column {i}: {title[:50]}...")
                        break

            if not column_indices:
                print("[ONS Retail Sales] No matching columns found")
                return None

            # データを格納
            result = {key: [] for key in self.SERIES_TITLES.keys()}

            for row in csv_reader:
                if len(row) < 2:
                    continue

                period_str = row[0].strip().strip('"')

                # 月次データのみを処理 (形式: "YYYY MMM")
                date_str = self._parse_ons_monthly_period(period_str)
                if not date_str:
                    continue

                for key, col_idx in column_indices.items():
                    if col_idx < len(row):
                        value_str = row[col_idx].strip().strip('"')
                        if value_str and value_str not in ['', '..', '-']:
                            try:
                                value = float(value_str)
                                result[key].append({
                                    "date": date_str,
                                    "value": round(value, 1),
                                    "period": period_str,
                                })
                            except ValueError:
                                continue

            for key, data in result.items():
                print(f"[ONS Retail Sales] Extracted {len(data)} {key} data points")

            return result

        except Exception as e:
            print(f"[ONS Retail Sales] Error parsing DRSI CSV: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_ons_monthly_period(self, period_str: str) -> Optional[str]:
        """ONSの月次形式 'YYYY MMM' を 'YYYY-MM-01' に変換"""
        month_map = {
            "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4,
            "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8,
            "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
        }

        try:
            parts = period_str.split()
            if len(parts) == 2:
                year = int(parts[0])
                month_str = parts[1].upper()
                if month_str in month_map:
                    month = month_map[month_str]
                    return f"{year}-{month:02d}-01"
        except (ValueError, IndexError):
            pass

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
                from services.uk.fmp_next_release_utils import should_refresh_by_pattern
                for pattern in self.FMP_EVENT_PATTERNS:
                    if should_refresh_by_pattern(pattern, last_updated_str, country="GB"):
                        print(f"[ONS Retail Sales] FMP pattern '{pattern}' indicates refresh needed")
                        return True
            except Exception as e:
                print(f"[ONS Retail Sales] Error checking FMP refresh: {e}")

            return False

        except Exception as e:
            print(f"[ONS Retail Sales] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ONS Retail Sales] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ONS Retail Sales] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ONS Retail Sales",
            "source": "Office for National Statistics",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "mom_count": len(cached_data.get("mom", [])) if cached_data else 0,
            "yoy_count": len(cached_data.get("yoy", [])) if cached_data else 0,
            "core_mom_count": len(cached_data.get("core_mom", [])) if cached_data else 0,
            "core_yoy_count": len(cached_data.get("core_yoy", [])) if cached_data else 0,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ons_retail_sales_service = ONSRetailSalesService()
