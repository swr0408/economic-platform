"""
NY Fed ACM Term Premium データサービス
Adrian, Crump, and Moench (ACM) モデルに基づくタームプレミアム推定値
"""
import io
from datetime import datetime
from typing import List, Dict, Any

import pandas as pd
import requests

from core.redis_client import redis_client, CACHE_TTL_DAY


class NYFedTermPremiumService:
    """NY Fed ACM タームプレミアム データサービス（日次データ、複数シリーズ対応）"""

    CACHE_KEY = "usa:term_premium:daily"
    CACHE_TTL = CACHE_TTL_DAY  # 24時間（毎日更新データ）

    def __init__(self):
        # NY Fed ACM Term Premium Excel URL
        self.excel_url = (
            "https://www.newyorkfed.org/medialibrary/media/research/"
            "data_indicators/ACMTermPremium.xls"
        )

    def get_term_premium_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        タームプレミアム関連データを取得

        Returns:
            {
                "data": [
                    {
                        "date": "2024-01-31",
                        "yield_10y": 4.05,      # 10年債利回り
                        "term_premium": 0.45,   # ACMタームプレミアム
                        "expected_rate": 3.60   # 期待短期金利
                    },
                    ...
                ],
                "cached": bool,
                "source": str,
                "last_updated": str
            }
        """
        # 1. Redisキャッシュをチェック
        if not force_refresh:
            cached_data = redis_client.get(self.CACHE_KEY)
            if cached_data:
                return {
                    "data": cached_data.get("data", []),
                    "cached": True,
                    "source": "redis",
                    "last_updated": cached_data.get("last_updated")
                }

        # 2. 外部APIからデータを取得
        api_data = self._fetch_from_external_api()

        if api_data:
            # Redisにキャッシュ
            cache_payload = {
                "data": api_data,
                "last_updated": datetime.now().isoformat()
            }
            redis_client.set(self.CACHE_KEY, cache_payload, expire=self.CACHE_TTL)

            return {
                "data": api_data,
                "cached": False,
                "source": "api",
                "last_updated": datetime.now().isoformat()
            }

        return {
            "data": [],
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available"
        }

    def _fetch_from_external_api(self) -> List[Dict[str, Any]]:
        """NY Fed から ACM Term Premium データを直接取得（複数シリーズ）"""
        try:
            print("Fetching ACM Term Premium from NY Fed...")

            response = requests.get(self.excel_url, timeout=60)
            response.raise_for_status()

            # Excelファイルを読み込み（日次データ: 'ACM Daily'シート）
            df = pd.read_excel(
                io.BytesIO(response.content),
                sheet_name='ACM Daily',
                header=0,
                engine='xlrd'
            )

            # 列名を確認
            # DATE: 日付
            # ACMY10: 10年債利回り (Yield)
            # ACMTP10: 10年タームプレミアム (Term Premium)
            # ACMRNY10: 10年期待短期金利 (Risk-Neutral Yield / Expected Short Rate)

            result = []
            for _, row in df.iterrows():
                try:
                    date_val = row['DATE']

                    # 日付の変換
                    if pd.isna(date_val):
                        continue

                    date_obj = pd.to_datetime(date_val)
                    formatted_date = date_obj.strftime('%Y-%m-%d')

                    # 各値を取得
                    yield_10y = row.get('ACMY10')
                    term_premium = row.get('ACMTP10')
                    expected_rate = row.get('ACMRNY10')

                    # 少なくとも1つの値が有効であれば追加
                    if pd.isna(yield_10y) and pd.isna(term_premium) and pd.isna(expected_rate):
                        continue

                    data_point = {
                        "date": formatted_date,
                        "yield_10y": round(float(yield_10y), 4) if pd.notna(yield_10y) else None,
                        "term_premium": round(float(term_premium), 4) if pd.notna(term_premium) else None,
                        "expected_rate": round(float(expected_rate), 4) if pd.notna(expected_rate) else None
                    }

                    result.append(data_point)
                except Exception:
                    continue

            result.sort(key=lambda x: x["date"])

            print(f"Fetched {len(result)} daily records from NY Fed ACM")
            return result

        except Exception as e:
            print(f"Error fetching from NY Fed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def invalidate_cache(self) -> bool:
        """Redisキャッシュを無効化"""
        return redis_client.delete(self.CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        cache_exists = redis_client.exists(self.CACHE_KEY)
        ttl = redis_client.ttl(self.CACHE_KEY) if cache_exists else -1

        return {
            "cache_key": self.CACHE_KEY,
            "exists": cache_exists,
            "ttl_seconds": ttl,
            "ttl_hours": round(ttl / 3600, 2) if ttl > 0 else 0
        }


# シングルトンインスタンス
nyfed_term_premium_service = NYFedTermPremiumService()
