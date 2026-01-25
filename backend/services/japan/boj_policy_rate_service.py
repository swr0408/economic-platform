"""
日銀政策金利（BOJ Policy Rate）サービス
DBから日銀金利決定データを取得

指標:
- BOJ Policy Rate: 日銀政策金利

データソース:
- DB: economic_calendar_events（FMP蓄積データ）
- CSV: 過去データインポート（日銀金利.csv）

発表スケジュール:
- 年8回（1月、3月、4月、6月、7月、9月、10月、12月）
- 発表時刻: 11:30～13:00 JST（変動あり）

注意:
- 発表日は11:30～13:00まで5分おきに発表されるためチェック
- データは%表記（例: 0.5%）

キャッシュ方式: FMP発表日時ベース判定方式
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client
from services.japan.fmp_next_release_utils import (
    get_next_release_from_fmp,
    should_refresh_by_fmp_schedule,
)


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュディレクトリ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "japan" / "monetary_policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "boj_policy_rate_cache.json"


class BOJPolicyRateService:
    """日銀政策金利サービス"""

    DATA_CACHE_KEY = "monetary_policy:boj_policy_rate:data"
    ECONALPHA_ID = "boj_policy_rate"

    def __init__(self):
        pass

    def get_boj_policy_rate_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        日銀政策金利データを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "forecast": float|null, "previous": float|null}, ...],
                "latest": {...},
                "next_release": {"date": "YYYY-MM-DD", "label": str} | null,
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "next_release": cached_data.get("next_release"),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str
                    }

        # DBから取得
        db_result = self._load_from_db()
        if db_result:
            next_release = get_next_release_from_fmp(self.ECONALPHA_ID)

            latest = db_result[-1] if db_result else None
            cache_payload = {
                "data": db_result,
                "latest": latest,
                "next_release": next_release,
                "last_updated": datetime.now(JST).isoformat()
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": db_result,
                "latest": latest,
                "next_release": next_release,
                "cached": False,
                "source": "database",
                "last_updated": datetime.now(JST).isoformat()
            }

        # 取得失敗時はファイルキャッシュから返す
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "next_release": file_cache.get("next_release"),
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "next_release": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _load_from_db(self) -> List[Dict[str, Any]]:
        """DBから履歴データを取得"""
        try:
            from core.database import SessionLocal
            from sqlalchemy import text

            with SessionLocal() as session:
                query = text("""
                    SELECT datetime_utc, event, actual, estimate, previous
                    FROM economic_calendar_events
                    WHERE country = 'JP'
                      AND (event ILIKE '%BoJ Interest Rate Decision%' OR event ILIKE '%BOJ Interest Rate%')
                      AND actual IS NOT NULL
                    ORDER BY datetime_utc ASC
                """)
                rows = session.execute(query).fetchall()

                result = []
                seen_dates = set()

                for row in rows:
                    dt_utc, event, actual, estimate, previous = row
                    if dt_utc:
                        # 日銀金利は発表日をそのまま日付として使用
                        date_str = dt_utc.strftime("%Y-%m-%d")

                        if date_str in seen_dates:
                            continue
                        seen_dates.add(date_str)

                        # actualの値を取得（%記号を除去してfloatに変換）
                        value = self._parse_rate_value(actual)
                        forecast = self._parse_rate_value(estimate)
                        prev_val = self._parse_rate_value(previous)

                        result.append({
                            "date": date_str,
                            "value": value,
                            "forecast": forecast,
                            "previous": prev_val,
                        })

                print(f"Loaded {len(result)} BOJ Policy Rate records from DB")
                return result

        except Exception as e:
            print(f"Error loading from DB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_rate_value(self, value: Any) -> Optional[float]:
        """金利値をパース（%記号対応、Decimal対応）"""
        if value is None:
            return None
        # Decimal型やint/float型
        try:
            return float(value)
        except (ValueError, TypeError):
            pass
        if isinstance(value, str):
            # %記号を除去してfloatに変換
            cleaned = value.replace('%', '').strip()
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP 5分方式）"""
        return should_refresh_by_fmp_schedule(self.ECONALPHA_ID, last_updated_str)

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込み"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None

            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cache saved to {DATA_CACHE_FILE}")
        except Exception as e:
            print(f"Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "BOJ Policy Rate",
            "source": "Database (FMP)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_from_fmp(self.ECONALPHA_ID),
            "file_cache_exists": DATA_CACHE_FILE.exists()
        }


# シングルトンインスタンス
boj_policy_rate_service = BOJPolicyRateService()
