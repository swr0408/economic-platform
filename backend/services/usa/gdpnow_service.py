"""
GDPNowサービス
Atlanta Fed GDPNow（リアルタイムGDP予測）データを取得

データソース:
- Atlanta Fed Excel: https://www.atlantafed.org/-/media/documents/cqer/researchcq/gdpnow/GDPTrackingModelDataAndForecasts.xlsx

発表スケジュール:
- 月に6-7回更新（経済指標発表の2-3時間後）
- 主要な更新タイミング:
  - ISM製造業景況指数発表後
  - 貿易収支発表後
  - 小売売上高発表後
  - 住宅着工件数発表後
  - 耐久財受注発表後
  - 個人所得発表後

キャッシュ方式: TTL方式（24時間）
- GDPNowは不定期更新のため、TTL方式で毎日チェック
"""
import io
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo

import requests
import pandas as pd

from core.redis_client import redis_client


# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")

# データソースURL
GDPNOW_EXCEL_URL = "https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/cqer/researchcq/gdpnow/GDPTrackingModelDataAndForecasts.xlsx"


class GDPNowService:
    """GDPNowサービス"""

    CACHE_KEY = "atlantafed:gdpnow"

    # キャッシュTTL: 24時間（秒）
    CACHE_TTL = 24 * 60 * 60

    def get_gdpnow_data(
        self,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        GDPNowデータを取得

        Args:
            force_refresh: キャッシュを無視して再取得

        Returns:
            {
                "data": [{"date": "YYYY-MM-DD", "value": float, "quarter": "YYYYQ#"}, ...],
                "latest": {"date": "YYYY-MM-DD", "value": float, "quarter": "YYYYQ#"},
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # キャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY)
            if cached_data:
                return {
                    "data": cached_data.get("data", []),
                    "latest": cached_data.get("latest"),
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached_data.get("last_updated")
                }

        # 外部APIから取得
        api_data = self._fetch_from_excel()

        if api_data:
            # 最新値を取得
            latest = api_data[-1] if api_data else None

            cache_payload = {
                "data": api_data,
                "latest": latest,
                "last_updated": datetime.now(JST).isoformat()
            }
            # TTL方式（24時間）
            redis_client.set(self.CACHE_KEY, cache_payload, expire=self.CACHE_TTL)

            return {
                "data": api_data,
                "latest": latest,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now(JST).isoformat()
            }

        # API取得失敗時: force_refreshでもRedisキャッシュにフォールバック
        cached_data = redis_client.get(self.CACHE_KEY)
        if cached_data:
            print("GDPNow API fetch failed, falling back to Redis cache")
            return {
                "data": cached_data.get("data", []),
                "latest": cached_data.get("latest"),
                "cached": True,
                "source": "redis (fallback)",
                "last_updated": cached_data.get("last_updated")
            }

        return {
            "data": [],
            "latest": None,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_excel(self) -> List[Dict[str, Any]]:
        """Atlanta Fed ExcelファイルからGDPNowデータを取得（TrackingHistoryシートのみ）"""
        try:
            print(f"Fetching GDPNow from Atlanta Fed Excel...")

            response = requests.get(GDPNOW_EXCEL_URL, timeout=60)
            response.raise_for_status()

            # Excelファイルを読み込み
            excel_data = io.BytesIO(response.content)

            # TrackingHistoryシートからデータを取得
            result = self._parse_tracking_history_sheet(excel_data)

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"Fetched {len(result)} records from Atlanta Fed Excel (GDPNow)")
            return result

        except Exception as e:
            print(f"Error fetching GDPNow from Excel: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_tracking_history_sheet(self, excel_data: io.BytesIO) -> List[Dict[str, Any]]:
        """TrackingHistoryシートからGDPNow予測を取得

        シート構造:
        - A2 (iloc[1,0]): "Evolution of GDP nowcast and components for 2025q3" → 四半期情報
        - Row 0: 日付ヘッダー（列2以降）
        - Row 30: A="GDP", B="GDP Nowcast" → GDPNow予測値の行
        """
        try:
            df = pd.read_excel(excel_data, sheet_name='TrackingHistory', header=None)

            result = []

            # A2セルから四半期を取得
            quarter_text = str(df.iloc[1, 0])  # "Evolution of GDP nowcast and components for 2025q3"
            quarter = self._extract_quarter_from_text(quarter_text)

            if not quarter:
                print(f"Could not extract quarter from: {quarter_text}")
                return []

            # GDP Nowcast行を探す（B列が"GDP Nowcast"の行）
            gdpnow_row = None
            for i in range(len(df)):
                b_val = df.iloc[i, 1]
                if pd.notna(b_val) and "GDP Nowcast" in str(b_val):
                    gdpnow_row = i
                    break

            if gdpnow_row is None:
                print("Could not find GDP Nowcast row")
                return []

            # 列2以降に日付と値がある
            # Row 0に日付、GDP Nowcast行に値
            for col_idx in range(2, len(df.columns)):
                date_val = df.iloc[0, col_idx]
                gdpnow_val = df.iloc[gdpnow_row, col_idx]

                # 日付の処理
                if pd.isna(date_val):
                    continue

                try:
                    if isinstance(date_val, datetime):
                        obs_date = date_val.strftime("%Y-%m-%d")
                    elif isinstance(date_val, date):
                        obs_date = date_val.strftime("%Y-%m-%d")
                    else:
                        continue
                except Exception:
                    continue

                # GDP値の処理
                if pd.isna(gdpnow_val):
                    continue

                try:
                    value = round(float(gdpnow_val), 2)
                except (ValueError, TypeError):
                    continue

                result.append({
                    "date": obs_date,
                    "value": value,
                    "quarter": quarter
                })

            return result

        except Exception as e:
            print(f"Error parsing TrackingHistory sheet: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _extract_quarter_from_text(self, text: str) -> Optional[str]:
        """テキストから四半期を抽出

        例: "Evolution of GDP nowcast and components for 2025q3" → "2025Q3"
        """
        import re
        # パターン: 年4桁 + q/Q + 四半期1桁
        match = re.search(r'(\d{4})[qQ](\d)', text)
        if match:
            year = match.group(1)
            q = match.group(2)
            return f"{year}Q{q}"
        return None

    def get_current_quarter_estimate(self) -> Optional[Dict[str, Any]]:
        """現在の四半期のGDPNow予測を取得"""
        result = self.get_gdpnow_data()
        return result.get("latest")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)
        ttl = redis_client.ttl(self.CACHE_KEY) if cache_exists else -1

        cached_data = redis_client.get(self.CACHE_KEY) if cache_exists else None

        return {
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "ttl_seconds": ttl,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None
        }


# シングルトンインスタンス
gdpnow_service = GDPNowService()
