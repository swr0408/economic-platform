"""
ONS GDP サービス
Office for National Statisticsからイギリスの実質GDPデータを取得

指標:
- ABMI: Gross Domestic Product: chained volume measures: Seasonally adjusted

データソース:
- ONS Time Series Data
- https://www.ons.gov.uk/economy/grossdomesticproductgdp/timeseries/abmi/ukea

発表スケジュール:
- 四半期ごと（速報、改定版を含む複数回）
- FMPカレンダーから次回発表日を取得

キャッシュ方式: Redis + ファイルキャッシュ（last_updated判定方式）
"""
import csv
import json
import requests
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.redis_client import redis_client

JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "economy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ons_gdp_cache.json"


class ONSGDPService:
    """ONS GDP サービス"""

    DATA_CACHE_KEY = "uk:ons_gdp:data"

    # ONS Time Series API - ABMI series (Real GDP, seasonally adjusted)
    # データセットは pn2 (Quarterly National Accounts) を使用。
    # 旧 ukea (UK Economic Accounts) は更新が約1四半期遅い（次回反映が QNA 確報まで遅延し
    # 直近四半期が取りこぼされる）ため、最も速報性の高い pn2 に切替。
    ABMI_CSV_URL = "https://www.ons.gov.uk/generator?format=csv&uri=/economy/grossdomesticproductgdp/timeseries/abmi/pn2"

    # FMPカレンダー検索パターン（indicator_event_mappingで定義されたもの）
    FMP_EVENT_PATTERNS = ["GDP Growth Rate QoQ", "GDP Growth Rate YoY", "Gross Domestic Product QoQ"]

    def __init__(self):
        pass

    def get_ons_gdp_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """ONS GDPデータを取得"""
        # 次回発表日を取得
        next_release = self._get_next_release()

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "qoq": cached_data.get("qoq", []),
                        "yoy": cached_data.get("yoy", []),
                        "quarterly_data": cached_data.get("quarterly_data", []),
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
                self.DATA_CACHE_KEY, ("qoq", "yoy", "quarterly_data"),
                _max_date_of(api_result.get("qoq", []), api_result.get("yoy", []), api_result.get("quarterly_data", [])), now_str
            )
            cache_payload = {
                "qoq": api_result.get("qoq", []),
                "yoy": api_result.get("yoy", []),
                "quarterly_data": api_result.get("quarterly_data", []),
                "metadata": api_result.get("metadata", {}),
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "qoq": api_result.get("qoq", []),
                "yoy": api_result.get("yoy", []),
                "quarterly_data": api_result.get("quarterly_data", []),
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
                "qoq": file_cache.get("qoq", []),
                "yoy": file_cache.get("yoy", []),
                "quarterly_data": file_cache.get("quarterly_data", []),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "qoq": [],
            "yoy": [],
            "quarterly_data": [],
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
            print(f"[ONS GDP] Error getting next release: {e}")
            return None

    def _fetch_from_ons(self) -> Optional[Dict[str, Any]]:
        """ONSからCSVデータを取得してパース"""
        try:
            print(f"[ONS GDP] Fetching data from {self.ABMI_CSV_URL}")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(self.ABMI_CSV_URL, headers=headers, timeout=30)
            response.raise_for_status()

            print(f"[ONS GDP] Received {len(response.text)} bytes")

            return self._parse_csv_data(response.text)

        except requests.exceptions.RequestException as e:
            print(f"[ONS GDP] Request error: {e}")
            return None
        except Exception as e:
            print(f"[ONS GDP] Error fetching from ONS: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_csv_data(self, csv_text: str) -> Optional[Dict[str, Any]]:
        """ONS CSVデータをパース"""
        try:
            csv_reader = csv.reader(StringIO(csv_text))

            # ヘッダー行を読み込む
            title_row = next(csv_reader)
            cdid_row = next(csv_reader)
            source_row = next(csv_reader)
            preunit_row = next(csv_reader)
            unit_row = next(csv_reader)
            release_date_row = next(csv_reader)
            next_release_row = next(csv_reader)
            notes_row = next(csv_reader)

            title = title_row[1] if len(title_row) > 1 else "GDP"
            cdid = cdid_row[1] if len(cdid_row) > 1 else ""
            unit = unit_row[1] if len(unit_row) > 1 else ""
            release_date = release_date_row[1] if len(release_date_row) > 1 else ""
            next_release = next_release_row[1] if len(next_release_row) > 1 else ""

            quarterly_data_points = []
            annual_data_points = []

            for row in csv_reader:
                if len(row) >= 2 and row[0] and row[1]:
                    try:
                        period_str = row[0].strip()
                        value = float(row[1].strip())

                        # 四半期データを処理 (形式: "YYYY QN")
                        if " Q" in period_str:
                            try:
                                year_str, quarter_str = period_str.split(" Q")
                                year = int(year_str)
                                quarter = int(quarter_str)

                                # 四半期を月に変換 (Q1=03, Q2=06, Q3=09, Q4=12)
                                month = quarter * 3
                                date_obj = datetime(year, month, 1)
                                date_str = date_obj.strftime("%Y-%m-01")

                                quarterly_data_points.append({
                                    "date": date_str,
                                    "value": round(value, 2),
                                    "period": period_str,
                                    "year": year,
                                    "quarter": quarter,
                                })
                            except ValueError:
                                continue
                        # 年次データを処理 (形式: "YYYY")
                        elif period_str.isdigit() and len(period_str) == 4:
                            try:
                                year = int(period_str)
                                date_obj = datetime(year, 12, 31)
                                date_str = date_obj.strftime("%Y-12-31")

                                annual_data_points.append({
                                    "date": date_str,
                                    "value": round(value, 2),
                                    "period": period_str,
                                    "year": year,
                                })
                            except ValueError:
                                continue
                    except (ValueError, IndexError):
                        continue

            print(f"[ONS GDP] Extracted {len(quarterly_data_points)} quarterly data points")

            # YoYとQoQの変化率を計算
            yoy_data = self._calculate_yoy_change(quarterly_data_points)
            qoq_data = self._calculate_qoq_change(quarterly_data_points)

            return {
                "quarterly_data": quarterly_data_points,
                "annual_data": annual_data_points,
                "yoy": yoy_data,
                "qoq": qoq_data,
                "metadata": {
                    "title": title,
                    "cdid": cdid,
                    "unit": unit,
                    "release_date": release_date,
                    "next_release_ons": next_release,
                    "source": "Office for National Statistics",
                    "description": "イギリス実質GDP（季節調整済み）",
                },
            }

        except Exception as e:
            print(f"[ONS GDP] Error parsing CSV: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _calculate_yoy_change(self, data_points: List[Dict]) -> List[Dict]:
        """前年同期比（YoY）の変化率を計算"""
        yoy_data = []
        sorted_data = sorted(data_points, key=lambda x: x["date"])

        for i, point in enumerate(sorted_data):
            if i >= 4:  # 4四半期前（1年前）が必要
                prev_point = sorted_data[i - 4]
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

    def _calculate_qoq_change(self, data_points: List[Dict]) -> List[Dict]:
        """前期比（QoQ）の変化率を計算"""
        qoq_data = []
        sorted_data = sorted(data_points, key=lambda x: x["date"])

        for i in range(1, len(sorted_data)):
            current_point = sorted_data[i]
            prev_point = sorted_data[i - 1]

            current_value = current_point["value"]
            prev_value = prev_point["value"]

            if prev_value and prev_value != 0:
                qoq_change = ((current_value - prev_value) / prev_value) * 100
                qoq_data.append({
                    "date": current_point["date"],
                    "period": current_point["period"],
                    "year": current_point["year"],
                    "quarter": current_point["quarter"],
                    "value": current_value,
                    "qoq_change": round(qoq_change, 2),
                })

        return qoq_data

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
                        print(f"[ONS GDP] FMP pattern '{pattern}' indicates refresh needed")
                        return True
            except Exception as e:
                print(f"[ONS GDP] Error checking FMP refresh: {e}")

            return False

        except Exception as e:
            print(f"[ONS GDP] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ONS GDP] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ONS GDP] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "ONS GDP",
            "source": "Office for National Statistics",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "qoq_count": len(cached_data.get("qoq", [])) if cached_data else 0,
            "yoy_count": len(cached_data.get("yoy", [])) if cached_data else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ons_gdp_service = ONSGDPService()
