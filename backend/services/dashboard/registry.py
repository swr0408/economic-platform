"""
ダッシュボードローダーレジストリ
国・カテゴリの組み合わせに対応するローダーを管理
"""
from typing import Dict, Tuple, Type, Optional
from fastapi import HTTPException

from services.dashboard.loaders.base import BaseDashboardLoader
from services.dashboard.loaders.usa_policy import USAPolicyLoader
from services.dashboard.loaders.usa_economy import USAEconomyLoader
from services.dashboard.loaders.usa_consumer import USAConsumerLoader
from services.dashboard.loaders.usa_employment import USAEmploymentLoader
from services.dashboard.loaders.usa_inflation import USAInflationLoader
from services.dashboard.loaders.usa_housing import USAHousingLoader
from services.dashboard.loaders.japan_policy import JapanPolicyLoader
from services.dashboard.loaders.japan_consumer import JapanConsumerLoader
from services.dashboard.loaders.japan_employment import JapanEmploymentLoader
from services.dashboard.loaders.japan_economy import JapanEconomyLoader
from services.dashboard.loaders.eurozone_policy import EurozonePolicyLoader
from services.dashboard.loaders.eurozone_economy import EurozoneEconomyLoader
from services.dashboard.loaders.eurozone_consumer import EurozoneConsumerLoader
from services.dashboard.loaders.eurozone_employment import EurozoneEmploymentLoader
from services.dashboard.loaders.eurozone_inflation import EurozoneInflationLoader
from services.dashboard.loaders.japan_price import JapanPriceLoader
from services.dashboard.loaders.uk_policy import UKPolicyLoader
from services.dashboard.loaders.uk_economy import UKEconomyLoader
from services.dashboard.loaders.uk_consumer import UKConsumerLoader
from services.dashboard.loaders.uk_employment import UKEmploymentLoader
from services.dashboard.loaders.uk_inflation import UKInflationLoader
from services.dashboard.loaders.uk_housing import UKHousingLoader


# ローダーレジストリ: (country, category) -> LoaderClass
DASHBOARD_LOADERS: Dict[Tuple[str, str], Type[BaseDashboardLoader]] = {
    # 米国
    ("usa", "policy"): USAPolicyLoader,
    ("usa", "economy"): USAEconomyLoader,
    ("usa", "consumer"): USAConsumerLoader,
    ("usa", "employment"): USAEmploymentLoader,
    ("usa", "inflation"): USAInflationLoader,
    ("usa", "housing"): USAHousingLoader,

    # 日本
    ("japan", "policy"): JapanPolicyLoader,
    ("japan", "economy"): JapanEconomyLoader,
    ("japan", "consumer"): JapanConsumerLoader,
    ("japan", "employment"): JapanEmploymentLoader,
    ("japan", "inflation"): JapanPriceLoader,

    # イギリス
    ("uk", "policy"): UKPolicyLoader,
    ("uk", "economy"): UKEconomyLoader,
    ("uk", "consumer"): UKConsumerLoader,
    ("uk", "employment"): UKEmploymentLoader,
    ("uk", "inflation"): UKInflationLoader,
    ("uk", "housing"): UKHousingLoader,

    # ユーロ圏
    ("eurozone", "policy"): EurozonePolicyLoader,
    ("eurozone", "economy"): EurozoneEconomyLoader,
    ("eurozone", "consumer"): EurozoneConsumerLoader,
    ("eurozone", "employment"): EurozoneEmploymentLoader,
    ("eurozone", "inflation"): EurozoneInflationLoader,

    # 他の国も同様に追加可能
}

# 利用可能な国コード
AVAILABLE_COUNTRIES = {
    "usa": "アメリカ",
    "japan": "日本",
    "eurozone": "ユーロ圏",
    "uk": "イギリス",
    "china": "中国",
    "australia": "オーストラリア",
    "newzealand": "ニュージーランド",
    "canada": "カナダ",
    "switzerland": "スイス",
}

# 利用可能なカテゴリコード
AVAILABLE_CATEGORIES = {
    "policy": "金融政策",
    "economy": "経済",
    "consumer": "消費",
    "employment": "雇用",
    "inflation": "物価",
    "housing": "住宅",
}


def get_dashboard_loader(country: str, category: str) -> BaseDashboardLoader:
    """
    国・カテゴリに対応するローダーインスタンスを取得

    Args:
        country: 国コード（例: "usa", "japan"）
        category: カテゴリコード（例: "policy", "economy"）

    Returns:
        BaseDashboardLoader のサブクラスインスタンス

    Raises:
        HTTPException: ローダーが見つからない場合
    """
    key = (country.lower(), category.lower())

    if key not in DASHBOARD_LOADERS:
        # 国コードが無効
        if country.lower() not in AVAILABLE_COUNTRIES:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown country: {country}. Available: {list(AVAILABLE_COUNTRIES.keys())}"
            )

        # カテゴリコードが無効
        if category.lower() not in AVAILABLE_CATEGORIES:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown category: {category}. Available: {list(AVAILABLE_CATEGORIES.keys())}"
            )

        # 国・カテゴリは有効だがローダーが未実装
        raise HTTPException(
            status_code=404,
            detail=f"Dashboard not yet available for {country}/{category}. Coming soon!"
        )

    loader_class = DASHBOARD_LOADERS[key]
    return loader_class()


def is_dashboard_available(country: str, category: str) -> bool:
    """ダッシュボードが利用可能かどうかを確認"""
    return (country.lower(), category.lower()) in DASHBOARD_LOADERS


def get_available_dashboards() -> list:
    """利用可能なダッシュボードのリストを取得"""
    return [
        {
            "country": country,
            "country_name": AVAILABLE_COUNTRIES.get(country, country),
            "category": category,
            "category_name": AVAILABLE_CATEGORIES.get(category, category),
        }
        for country, category in DASHBOARD_LOADERS.keys()
    ]
