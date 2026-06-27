"""
UK ONS平均賃金サービス
ONS Time Series APIから賃金伸び率データを取得

指標:
- KAC3: Total Pay (including bonuses) YoY growth %
- KAI9: Regular Pay (excluding bonuses) YoY growth %

データソース:
- ONS Time Series Data
- https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours

発表スケジュール:
- ONS公式サイトの「Next release」日程に基づく
- 15:00-16:10 ロンドン時間

キャッシュ方式: Redis + ファイルキャッシュ（FMP発表日時ベース判定）
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


JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "employment"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ons_wages_cache.json"


class ONSWagesService:
    """UK ONS平均賃金サービス"""

    DATA_CACHE_KEY = "uk:ons_wages:data"
    ECONALPHA_ID = "ons_wages"

    # ONS Time Series API URLs
    # KAC3: Total Pay (including bonuses) YoY growth %
    TOTAL_PAY_CSV_URL = "https://www.ons.gov.uk/generator?format=csv&uri=/employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kac3/lms"
    # KAI9: Regular Pay (excluding bonuses) YoY growth %
    REGULAR_PAY_CSV_URL = "https://www.ons.gov.uk/generator?format=csv&uri=/employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kai9/lms"

    # FMPカレンダー検索パターン
    FMP_EVENT_PATTERNS = [
        "Average Earnings excl. Bonus",
        "Average Earnings excl. Bonus (3Mo/Yr)",
        "Average Earnings incl. Bonus"
    ]

    def __init__(self):
        pass

    def get_ons_wages_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ONS平均賃金データを取得"""
        # 次回発表日を取得
        next_release = self._get_next_release()

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
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
            latest = api_result["data"][-1] if api_result["data"] else None

            # 発表時刻レース対策（ラグガード）: 取得データが新月に進んでいない場合は
            # last_updated を発表直前に据え置き、ONS反映後の再取得を促す。
            from services.uk.fmp_next_release_utils import resolve_last_updated_after_fetch
            _prev_cache = redis_client.get(self.DATA_CACHE_KEY)
            _prev_latest = _prev_cache.get("latest") if isinstance(_prev_cache, dict) else None
            _resolved_last_updated = resolve_last_updated_after_fetch(
                getattr(self, "FMP_EVENT_PATTERNS", None) or getattr(self, "FMP_EVENT_PATTERN", None),
                latest.get("date") if isinstance(latest, dict) else None,
                _prev_latest.get("date") if isinstance(_prev_latest, dict) else None,
                _prev_cache.get("last_updated") if isinstance(_prev_cache, dict) else None,
                country="GB",
            )

            cache_payload = {
                "data": api_result["data"],
                "latest": latest,
                "metadata": api_result.get("metadata", {}),
                "last_updated": _resolved_last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": api_result["data"],
                "latest": latest,
                "metadata": api_result.get("metadata", {}),
                "next_release": next_release,
                "cached": False,
                "source": "ons_api",
                "last_updated": _resolved_last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
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
            from services.uk.fmp_next_release_utils import get_next_release_by_pattern

            # 複数のパターンで検索し、最も近いものを返す
            candidates = []
            for pattern in self.FMP_EVENT_PATTERNS:
                result = get_next_release_by_pattern(pattern, country="GB")
                if result:
                    candidates.append(result)

            if candidates:
                # 日付が最も近いものを選択
                candidates.sort(key=lambda x: x.get("date", ""))
                return candidates[0]

            return None
        except Exception as e:
            print(f"[ONS Wages] Error getting next release: {e}")
            return None

    def _fetch_from_ons(self) -> Optional[Dict[str, Any]]:
        """ONSから両系列のCSVデータを取得してパース"""
        try:
            print(f"[ONS Wages] Fetching Total Pay data from {self.TOTAL_PAY_CSV_URL}")
            total_pay_data = self._parse_csv_data(self.TOTAL_PAY_CSV_URL, "Total Pay (KAC3)")
            if not total_pay_data:
                return None

            print(f"[ONS Wages] Fetching Regular Pay data from {self.REGULAR_PAY_CSV_URL}")
            regular_pay_data = self._parse_csv_data(self.REGULAR_PAY_CSV_URL, "Regular Pay (KAI9)")
            if not regular_pay_data:
                return None

            # 両系列を統合
            return self._combine_series(total_pay_data, regular_pay_data)

        except Exception as e:
            print(f"[ONS Wages] Error fetching from ONS: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_csv_data(self, csv_url: str, series_name: str) -> Optional[Dict[str, Any]]:
        """ONS CSVデータをパース"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(csv_url, headers=headers, timeout=30)
            response.raise_for_status()

            print(f"[ONS Wages] Received {len(response.text)} bytes for {series_name}")

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
            next_release = next_release_row[1] if len(next_release_row) > 1 else ""

            data_points = []

            month_map = {
                "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4,
                "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8,
                "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
            }

            for row in csv_reader:
                if len(row) >= 2 and row[0] and row[1]:
                    try:
                        period_str = row[0].strip()
                        value = float(row[1].strip())

                        # 月次データを処理 (形式: "YYYY MMM" 例: "2024 JAN")
                        if " " in period_str and len(period_str.split()) == 2:
                            parts = period_str.split()
                            if len(parts[0]) == 4 and parts[0].isdigit():
                                year_str = parts[0]
                                month_str = parts[1].upper()

                                # 四半期データをスキップ
                                if month_str.startswith('Q'):
                                    continue

                                if month_str in month_map:
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

            # 日付でソート
            data_points.sort(key=lambda x: x["date"])

            print(f"[ONS Wages] Extracted {len(data_points)} data points for {series_name}")

            return {
                "data": data_points,
                "metadata": {
                    "title": title,
                    "cdid": cdid,
                    "unit": unit,
                    "release_date": release_date,
                    "next_release_ons": next_release,
                },
            }

        except Exception as e:
            print(f"[ONS Wages] Error parsing CSV for {series_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _combine_series(
        self, total_pay_data: Dict[str, Any], regular_pay_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """両系列を統合"""
        combined_data = {}

        # Total Pay データを追加
        for point in total_pay_data["data"]:
            date = point["date"]
            combined_data[date] = {
                "date": date,
                "total_pay": point["value"],
                "regular_pay": None,
            }

        # Regular Pay データを追加
        for point in regular_pay_data["data"]:
            date = point["date"]
            if date in combined_data:
                combined_data[date]["regular_pay"] = point["value"]
            else:
                combined_data[date] = {
                    "date": date,
                    "total_pay": None,
                    "regular_pay": point["value"],
                }

        # ソートしてリストに変換
        sorted_data = sorted(combined_data.values(), key=lambda x: x["date"])

        print(f"[ONS Wages] Combined {len(sorted_data)} data points")

        return {
            "data": sorted_data,
            "metadata": {
                "total_pay_title": total_pay_data["metadata"]["title"],
                "total_pay_cdid": total_pay_data["metadata"]["cdid"],
                "regular_pay_title": regular_pay_data["metadata"]["title"],
                "regular_pay_cdid": regular_pay_data["metadata"]["cdid"],
                "unit": "%",
                "release_date": total_pay_data["metadata"]["release_date"],
                "next_release_ons": total_pay_data["metadata"]["next_release_ons"],
                "source": "Office for National Statistics",
                "description": "イギリス平均週給（前年比）",
            },
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """
        キャッシュを更新すべきかどうかを判定

        ロジック:
        - 7日以上経過していれば更新
        - FMPの発表日付近は頻繁にチェック
        """
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
                        print(f"[ONS Wages] FMP pattern '{pattern}' indicates refresh needed")
                        return True
            except Exception as e:
                print(f"[ONS Wages] Error checking FMP refresh: {e}")

            return False

        except Exception as e:
            print(f"[ONS Wages] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ONS Wages] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ONS Wages] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ONS Wages",
            "source": "Office for National Statistics",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ons_wages_service = ONSWagesService()
