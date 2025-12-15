"""
日本 消費者物価指数 (CPI) データサービス
e-Stat API を使用
"""
from typing import List, Dict, Any

import requests

from services.base_economic_service import BaseEconomicService


class JapanCPIService(BaseEconomicService):
    """日本CPI（消費者物価指数）データサービス"""

    # 基底クラスの設定
    INDICATOR_CODE = "JP_CPI"
    CACHE_KEY_PREFIX = "japan:cpi"

    def __init__(self):
        # e-Stat API の設定
        # 実際のAPI実装時にURLを設定
        self.api_url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
        self.app_id = ""  # e-Stat APIキー

    def _get_unit(self) -> str:
        """単位を取得"""
        return "index"  # 指数

    def _fetch_from_external_api(self) -> List[Dict[str, Any]]:
        """
        e-Stat API から日本CPIデータを取得

        TODO: 実際のAPI実装
        - e-Stat APIキーの設定
        - statsDataId の指定
        - レスポンスのパース
        """
        try:
            print("Fetching Japan CPI from e-Stat API...")

            # TODO: 実際のAPI呼び出し実装
            # params = {
            #     "appId": self.app_id,
            #     "statsDataId": "0003143513",  # CPI統計表ID
            #     "cdTime": "2020-2024"
            # }
            # response = requests.get(self.api_url, params=params, timeout=30)
            # response.raise_for_status()
            # data = response.json()

            # パース処理
            # result = self._parse_estat_response(data)

            # プレースホルダー
            result = []

            print(f"Fetched {len(result)} records from e-Stat API")
            return result

        except Exception as e:
            print(f"Error fetching Japan CPI: {e}")
            import traceback
            traceback.print_exc()
            return []


# シングルトンインスタンス
japan_cpi_service = JapanCPIService()
