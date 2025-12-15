"""
Federal Reserve 政策金利データサービス
FRED API (DFEDTARU) を使用して政策金利を取得

Data Source: https://fred.stlouisfed.org/series/DFEDTARU
"""
from typing import Dict, Any

from services.usa.fred_service import fred_service


class FedH15Service:
    """
    連邦準備制度 政策金利データサービス

    FRED API経由でFederal Funds Target Rate Upper Bound (DFEDTARU) を取得
    """

    SERIES_ID = "DFEDTARU"

    def __init__(self):
        pass

    def get_policy_rate(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        政策金利データを取得

        FRED Series: DFEDTARU (Federal Funds Target Rate - Upper Bound)
        Source: https://fred.stlouisfed.org/series/DFEDTARU
        """
        return fred_service.get_policy_rate(force_refresh=force_refresh)

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """後方互換性のためのエイリアス"""
        return self.get_policy_rate(force_refresh=force_refresh)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得"""
        return fred_service.get_cache_status(self.SERIES_ID)

    def refresh_cache(self) -> bool:
        """キャッシュを強制更新"""
        result = fred_service.get_policy_rate(force_refresh=True)
        return bool(result.get("data"))

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return fred_service.invalidate_cache(self.SERIES_ID)


# シングルトンインスタンス
fed_h15_service = FedH15Service()
