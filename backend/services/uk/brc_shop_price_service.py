"""
BRC店頭価格指数サービス
CSVから履歴データ、FMPから最新値を取得

指標:
- BRC Shop Price Index（前年比）

データソース:
- CSV: 過去データ（2010年〜）
- DB: economic_calendar_events（FMP蓄積データ・最新値更新用）

発表スケジュール:
- 毎月末〜翌月初
- 月末発表時は当月分データ、月初発表時は前月分データ

キャッシュ方式: FMP発表日時ベース判定方式
"""
import csv
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "uk" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "brc_shop_price_cache.json"

# CSVファイルパス
CSV_FILE = Path(__file__).parent.parent.parent / "data" / "csv_import" / "BRC店頭価格指数.csv"


class BRCShopPriceService:
    """BRC店頭価格指数サービス"""

    DATA_CACHE_KEY = "uk:brc_shop_price:data"
    ECONALPHA_ID = "brc_shop_price"

    # FMPカレンダー検索パターン
    FMP_EVENT_PATTERNS = ["BRC Shop Price Index YoY"]

    def __init__(self):
        pass

    def get_brc_shop_price_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """BRC店頭価格指数データを取得"""
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
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # CSVから履歴データを取得
        csv_data = self._load_from_csv()

        # DBから最新値を取得してマージ
        db_data = self._load_latest_from_db()
        merged_data = self._merge_data(csv_data, db_data)

        if merged_data:
            latest = merged_data[-1] if merged_data else None

            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )
            cache_payload = {
                "data": merged_data,
                "latest": latest,
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": merged_data,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "csv+database",
                "last_updated": datetime.now(JST).isoformat(),
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
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
            print(f"[BRC Shop Price] Error getting next release: {e}")
            return None

    def _load_from_csv(self) -> List[Dict[str, Any]]:
        """CSVから履歴データを取得

        CSVフォーマット:
        公表日時,発表時間,結果,予想,前回
        2010/1,,2.3,,
        2024/12,9:01,-1,-0.4,-0.6

        注意: 公表日時（2024/12）は発表月であり、データ対象月でもある
        月末発表時は当月分、月初発表時は前月分として解釈
        """
        try:
            if not CSV_FILE.exists():
                print(f"[BRC Shop Price] CSV file not found: {CSV_FILE}")
                return []

            result = []
            with open(CSV_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date_str = row.get("公表日時", "").strip()
                    if not date_str:
                        continue

                    # パース: 2024/12 → 2024-12-01
                    try:
                        parts = date_str.split("/")
                        if len(parts) != 2:
                            continue
                        year = int(parts[0])
                        month = int(parts[1])
                        iso_date = f"{year}-{month:02d}-01"
                    except (ValueError, IndexError):
                        continue

                    # 値をパース
                    actual_str = row.get("結果", "").strip()
                    forecast_str = row.get("予想", "").strip()
                    previous_str = row.get("前回", "").strip()

                    if not actual_str:
                        continue

                    try:
                        actual = float(actual_str)
                    except ValueError:
                        continue

                    result.append({
                        "date": iso_date,
                        "value": actual,
                        "forecast": float(forecast_str) if forecast_str else None,
                        "previous": float(previous_str) if previous_str else None,
                    })

            print(f"[BRC Shop Price] Loaded {len(result)} records from CSV")
            return result

        except Exception as e:
            print(f"[BRC Shop Price] Error loading from CSV: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _load_latest_from_db(self) -> List[Dict[str, Any]]:
        """DBから最新データを取得（FMP蓄積データ）

        注意: FMPの発表日から対象月を判定
        - 月末（25日以降）発表: 当月データ
        - 月初（1日〜10日）発表: 前月データ
        """
        try:
            from core.database import SessionLocal
            from sqlalchemy import text
            from dateutil.relativedelta import relativedelta

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'UK'
                      AND event ILIKE '%BRC Shop Price Index YoY%'
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, actual, estimate, previous = row
                    if dt_utc:
                        # 発表日に基づいてデータ対象月を決定
                        day_of_month = dt_utc.day

                        if day_of_month >= 25:
                            # 月末発表: 当月データ
                            data_month = dt_utc
                        elif day_of_month <= 10:
                            # 月初発表: 前月データ
                            data_month = dt_utc - relativedelta(months=1)
                        else:
                            # 中旬発表: 通常は前月データとして扱う
                            data_month = dt_utc - relativedelta(months=1)

                        date_str = data_month.strftime("%Y-%m-01")

                        if date_str in seen_dates:
                            continue
                        seen_dates.add(date_str)

                        result.append({
                            "date": date_str,
                            "value": float(actual) if actual else None,
                            "forecast": float(estimate) if estimate else None,
                            "previous": float(previous) if previous else None,
                        })

                print(f"[BRC Shop Price] Loaded {len(result)} records from DB")
                return result

        except Exception as e:
            print(f"[BRC Shop Price] Error loading from DB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _merge_data(
        self, csv_data: List[Dict[str, Any]], db_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """CSVデータとDBデータをマージ

        CSVをベースに、DBの新しいデータで更新/追加
        """
        # 日付をキーにしたマップを作成
        data_map = {}

        # まずCSVデータを追加
        for item in csv_data:
            data_map[item["date"]] = item

        # DBデータで上書き/追加（DBの方が新しいと仮定）
        for item in db_data:
            data_map[item["date"]] = item

        # 日付順にソートして返す
        result = sorted(data_map.values(), key=lambda x: x["date"])
        print(f"[BRC Shop Price] Merged data: {len(result)} records")
        return result

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
                        print(f"[BRC Shop Price] FMP pattern '{pattern}' indicates refresh needed")
                        return True
            except Exception as e:
                print(f"[BRC Shop Price] Error checking FMP refresh: {e}")

            return False

        except Exception as e:
            print(f"[BRC Shop Price] Error in should_refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[BRC Shop Price] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[BRC Shop Price] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "BRC Shop Price Index",
            "source": "CSV + Database (FMP)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": self._get_next_release(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "csv_file_exists": CSV_FILE.exists(),
        }


# シングルトンインスタンス
brc_shop_price_service = BRCShopPriceService()
