"""
Dukascopy対応銘柄マスタ

マーケットインパクト機能で使用可能な銘柄一覧
カテゴリ: FX（為替）、IDX（株価指数）、CMD（商品）、BND（債券）
"""
from typing import Dict, List, Any, Optional


# Dukascopy銘柄定義
# id: 内部ID, name: 日本語名, name_en: 英語名, category: カテゴリ, sub_category: サブカテゴリ
DUKASCOPY_SYMBOLS: List[Dict[str, Any]] = [
    # ===========================
    # FX - メジャー通貨ペア
    # ===========================
    {"id": "usdjpy", "name": "ドル/円", "name_en": "USD/JPY", "category": "forex", "sub_category": "major", "dukascopy_const": "INSTRUMENT_FX_MAJORS_USD_JPY"},
    {"id": "eurusd", "name": "ユーロ/ドル", "name_en": "EUR/USD", "category": "forex", "sub_category": "major", "dukascopy_const": "INSTRUMENT_FX_MAJORS_EUR_USD"},
    {"id": "gbpusd", "name": "ポンド/ドル", "name_en": "GBP/USD", "category": "forex", "sub_category": "major", "dukascopy_const": "INSTRUMENT_FX_MAJORS_GBP_USD"},
    {"id": "audusd", "name": "豪ドル/ドル", "name_en": "AUD/USD", "category": "forex", "sub_category": "major", "dukascopy_const": "INSTRUMENT_FX_MAJORS_AUD_USD"},
    {"id": "nzdusd", "name": "NZドル/ドル", "name_en": "NZD/USD", "category": "forex", "sub_category": "major", "dukascopy_const": "INSTRUMENT_FX_MAJORS_NZD_USD"},
    {"id": "usdcad", "name": "ドル/カナダドル", "name_en": "USD/CAD", "category": "forex", "sub_category": "major", "dukascopy_const": "INSTRUMENT_FX_MAJORS_USD_CAD"},
    {"id": "usdchf", "name": "ドル/スイスフラン", "name_en": "USD/CHF", "category": "forex", "sub_category": "major", "dukascopy_const": "INSTRUMENT_FX_MAJORS_USD_CHF"},

    # ===========================
    # FX - クロス円
    # ===========================
    {"id": "eurjpy", "name": "ユーロ/円", "name_en": "EUR/JPY", "category": "forex", "sub_category": "jpy_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_EUR_JPY"},
    {"id": "gbpjpy", "name": "ポンド/円", "name_en": "GBP/JPY", "category": "forex", "sub_category": "jpy_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_GBP_JPY"},
    {"id": "audjpy", "name": "豪ドル/円", "name_en": "AUD/JPY", "category": "forex", "sub_category": "jpy_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_AUD_JPY"},
    {"id": "nzdjpy", "name": "NZドル/円", "name_en": "NZD/JPY", "category": "forex", "sub_category": "jpy_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_NZD_JPY"},
    {"id": "cadjpy", "name": "カナダドル/円", "name_en": "CAD/JPY", "category": "forex", "sub_category": "jpy_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_CAD_JPY"},
    {"id": "chfjpy", "name": "スイスフラン/円", "name_en": "CHF/JPY", "category": "forex", "sub_category": "jpy_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_CHF_JPY"},

    # ===========================
    # FX - ユーロクロス
    # ===========================
    {"id": "eurgbp", "name": "ユーロ/ポンド", "name_en": "EUR/GBP", "category": "forex", "sub_category": "eur_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_EUR_GBP"},
    {"id": "euraud", "name": "ユーロ/豪ドル", "name_en": "EUR/AUD", "category": "forex", "sub_category": "eur_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_EUR_AUD"},
    {"id": "eurnzd", "name": "ユーロ/NZドル", "name_en": "EUR/NZD", "category": "forex", "sub_category": "eur_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_EUR_NZD"},
    {"id": "eurcad", "name": "ユーロ/カナダドル", "name_en": "EUR/CAD", "category": "forex", "sub_category": "eur_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_EUR_CAD"},
    {"id": "eurchf", "name": "ユーロ/スイスフラン", "name_en": "EUR/CHF", "category": "forex", "sub_category": "eur_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_EUR_CHF"},

    # ===========================
    # FX - ポンドクロス
    # ===========================
    {"id": "gbpaud", "name": "ポンド/豪ドル", "name_en": "GBP/AUD", "category": "forex", "sub_category": "gbp_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_GBP_AUD"},
    {"id": "gbpnzd", "name": "ポンド/NZドル", "name_en": "GBP/NZD", "category": "forex", "sub_category": "gbp_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_GBP_NZD"},
    {"id": "gbpcad", "name": "ポンド/カナダドル", "name_en": "GBP/CAD", "category": "forex", "sub_category": "gbp_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_GBP_CAD"},
    {"id": "gbpchf", "name": "ポンド/スイスフラン", "name_en": "GBP/CHF", "category": "forex", "sub_category": "gbp_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_GBP_CHF"},

    # ===========================
    # FX - その他クロス
    # ===========================
    {"id": "audcad", "name": "豪ドル/カナダドル", "name_en": "AUD/CAD", "category": "forex", "sub_category": "other_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_AUD_CAD"},
    {"id": "audchf", "name": "豪ドル/スイスフラン", "name_en": "AUD/CHF", "category": "forex", "sub_category": "other_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_AUD_CHF"},
    {"id": "audnzd", "name": "豪ドル/NZドル", "name_en": "AUD/NZD", "category": "forex", "sub_category": "other_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_AUD_NZD"},
    {"id": "nzdcad", "name": "NZドル/カナダドル", "name_en": "NZD/CAD", "category": "forex", "sub_category": "other_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_NZD_CAD"},
    {"id": "nzdchf", "name": "NZドル/スイスフラン", "name_en": "NZD/CHF", "category": "forex", "sub_category": "other_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_NZD_CHF"},
    {"id": "cadchf", "name": "カナダドル/スイスフラン", "name_en": "CAD/CHF", "category": "forex", "sub_category": "other_cross", "dukascopy_const": "INSTRUMENT_FX_CROSSES_CAD_CHF"},

    # ===========================
    # FX - 貴金属
    # ===========================
    {"id": "xauusd", "name": "ゴールド", "name_en": "Gold (XAU/USD)", "category": "forex", "sub_category": "metal", "dukascopy_const": "INSTRUMENT_FX_METALS_XAU_USD"},
    {"id": "xagusd", "name": "シルバー", "name_en": "Silver (XAG/USD)", "category": "forex", "sub_category": "metal", "dukascopy_const": "INSTRUMENT_FX_METALS_XAG_USD"},

    # ===========================
    # 株価指数 - 米国
    # ===========================
    {"id": "sp500", "name": "S&P500", "name_en": "S&P 500", "category": "index", "sub_category": "us", "dukascopy_const": "INSTRUMENT_IDX_AMERICA_E_SANDP_500"},
    {"id": "dow", "name": "NYダウ", "name_en": "Dow Jones", "category": "index", "sub_category": "us", "dukascopy_const": "INSTRUMENT_IDX_AMERICA_E_D_J_IND"},
    {"id": "nasdaq100", "name": "ナスダック100", "name_en": "Nasdaq 100", "category": "index", "sub_category": "us", "dukascopy_const": "INSTRUMENT_IDX_AMERICA_E_NQ_100"},
    {"id": "russell2000", "name": "ラッセル2000", "name_en": "Russell 2000", "category": "index", "sub_category": "us", "dukascopy_const": "INSTRUMENT_IDX_AMERICA_RUSSELL_IDX_USD"},
    {"id": "ussc2000", "name": "米国小型株2000", "name_en": "US Small Cap 2000", "category": "index", "sub_category": "us", "dukascopy_const": "INSTRUMENT_IDX_AMERICA_USSC2000_IDX_USD"},
    {"id": "vix", "name": "VIX恐怖指数", "name_en": "VIX Volatility Index", "category": "index", "sub_category": "us", "dukascopy_const": "INSTRUMENT_IDX_AMERICA_VOL_IDX_USD"},
    {"id": "dxy", "name": "ドルインデックス", "name_en": "US Dollar Index", "category": "index", "sub_category": "us", "dukascopy_const": "INSTRUMENT_IDX_AMERICA_DOLLAR_IDX_USD"},

    # ===========================
    # 株価指数 - アジア
    # ===========================
    {"id": "nikkei225", "name": "日経225", "name_en": "Nikkei 225", "category": "index", "sub_category": "asia", "dukascopy_const": "INSTRUMENT_IDX_ASIA_E_N225JAP"},
    {"id": "hsi", "name": "香港ハンセン", "name_en": "Hang Seng Index", "category": "index", "sub_category": "asia", "dukascopy_const": "INSTRUMENT_IDX_ASIA_E_H_KONG"},
    {"id": "china50", "name": "中国50", "name_en": "China 50", "category": "index", "sub_category": "asia", "dukascopy_const": "INSTRUMENT_IDX_ASIA_CHI_IDX_USD"},

    # ===========================
    # 株価指数 - 欧州
    # ===========================
    {"id": "dax", "name": "独DAX", "name_en": "DAX 40", "category": "index", "sub_category": "europe", "dukascopy_const": "INSTRUMENT_IDX_EUROPE_E_DAAX"},
    {"id": "ftse100", "name": "英FTSE100", "name_en": "FTSE 100", "category": "index", "sub_category": "europe", "dukascopy_const": "INSTRUMENT_IDX_EUROPE_E_FUTSEE_100"},
    {"id": "cac40", "name": "仏CAC40", "name_en": "CAC 40", "category": "index", "sub_category": "europe", "dukascopy_const": "INSTRUMENT_IDX_EUROPE_E_CAAC_40"},
    {"id": "eurostoxx50", "name": "ユーロストックス50", "name_en": "Euro Stoxx 50", "category": "index", "sub_category": "europe", "dukascopy_const": "INSTRUMENT_IDX_EUROPE_E_DJE50XX"},

    # ===========================
    # 商品 - エネルギー
    # ===========================
    {"id": "wti", "name": "WTI原油", "name_en": "WTI Crude Oil", "category": "commodity", "sub_category": "energy", "dukascopy_const": "INSTRUMENT_CMD_ENERGY_E_LIGHT"},
    {"id": "brent", "name": "ブレント原油", "name_en": "Brent Crude Oil", "category": "commodity", "sub_category": "energy", "dukascopy_const": "INSTRUMENT_CMD_ENERGY_E_BRENT"},
    {"id": "natgas", "name": "天然ガス", "name_en": "Natural Gas", "category": "commodity", "sub_category": "energy", "dukascopy_const": "INSTRUMENT_CMD_ENERGY_GAS_CMD_USD"},

    # ===========================
    # 商品 - 金属
    # ===========================
    {"id": "copper", "name": "銅", "name_en": "Copper", "category": "commodity", "sub_category": "metal", "dukascopy_const": "INSTRUMENT_CMD_METALS_COPPER_CMD_USD"},
    {"id": "platinum", "name": "プラチナ", "name_en": "Platinum", "category": "commodity", "sub_category": "metal", "dukascopy_const": "INSTRUMENT_CMD_METALS_XPT_CMD_USD"},
    {"id": "palladium", "name": "パラジウム", "name_en": "Palladium", "category": "commodity", "sub_category": "metal", "dukascopy_const": "INSTRUMENT_CMD_METALS_XPD_CMD_USD"},

    # ===========================
    # 商品 - 農産物
    # ===========================
    {"id": "cocoa", "name": "ココア", "name_en": "Cocoa", "category": "commodity", "sub_category": "agricultural", "dukascopy_const": "INSTRUMENT_CMD_AGRICULTURAL_COCOA_CMD_USD"},
    {"id": "coffee", "name": "コーヒー", "name_en": "Coffee", "category": "commodity", "sub_category": "agricultural", "dukascopy_const": "INSTRUMENT_CMD_AGRICULTURAL_COFFEE_CMD_USX"},
    {"id": "cotton", "name": "綿花", "name_en": "Cotton", "category": "commodity", "sub_category": "agricultural", "dukascopy_const": "INSTRUMENT_CMD_AGRICULTURAL_COTTON_CMD_USX"},
    {"id": "sugar", "name": "砂糖", "name_en": "Sugar", "category": "commodity", "sub_category": "agricultural", "dukascopy_const": "INSTRUMENT_CMD_AGRICULTURAL_SUGAR_CMD_USD"},
    {"id": "soybean", "name": "大豆", "name_en": "Soybean", "category": "commodity", "sub_category": "agricultural", "dukascopy_const": "INSTRUMENT_CMD_AGRICULTURAL_SOYBEAN_CMD_USX"},
    {"id": "orange_juice", "name": "オレンジジュース", "name_en": "Orange Juice", "category": "commodity", "sub_category": "agricultural", "dukascopy_const": "INSTRUMENT_CMD_AGRICULTURAL_OJUICE_CMD_USX"},

    # ===========================
    # 債券
    # ===========================
    {"id": "us_tbond", "name": "米国債30年", "name_en": "US T-Bond", "category": "bond", "sub_category": "government", "dukascopy_const": "INSTRUMENT_BND_CFD_USTBOND_TR_USD"},
    {"id": "bund", "name": "独連邦債", "name_en": "German Bund", "category": "bond", "sub_category": "government", "dukascopy_const": "INSTRUMENT_BND_CFD_BUND_TR_EUR"},
    {"id": "uk_gilt", "name": "英国債", "name_en": "UK Gilt", "category": "bond", "sub_category": "government", "dukascopy_const": "INSTRUMENT_BND_CFD_UKGILT_TR_GBP"},
]


# カテゴリ定義
DUKASCOPY_CATEGORIES = {
    "forex": "為替",
    "index": "株価指数",
    "commodity": "商品",
    "bond": "債券",
}

DUKASCOPY_SUB_CATEGORIES = {
    # 為替
    "major": "メジャー通貨ペア",
    "jpy_cross": "クロス円",
    "eur_cross": "ユーロクロス",
    "gbp_cross": "ポンドクロス",
    "other_cross": "その他クロス",
    "usd_cross": "ドルクロス（新興国）",
    "metal": "貴金属",
    # 株価指数
    "us": "米国",
    "asia": "アジア",
    "europe": "欧州",
    "other": "その他",
    # 商品
    "energy": "エネルギー",
    "agricultural": "農産物",
    # 債券
    "government": "国債",
}


def get_all_dukascopy_symbols() -> List[Dict[str, Any]]:
    """全Dukascopy銘柄を取得"""
    return DUKASCOPY_SYMBOLS


def get_dukascopy_symbol_by_id(symbol_id: str) -> Optional[Dict[str, Any]]:
    """IDで銘柄を取得"""
    for symbol in DUKASCOPY_SYMBOLS:
        if symbol["id"] == symbol_id:
            return symbol
    return None


def get_dukascopy_symbols_by_category(category: str) -> List[Dict[str, Any]]:
    """カテゴリで銘柄をフィルタ"""
    return [s for s in DUKASCOPY_SYMBOLS if s["category"] == category]


def get_dukascopy_symbols_by_sub_category(sub_category: str) -> List[Dict[str, Any]]:
    """サブカテゴリで銘柄をフィルタ"""
    return [s for s in DUKASCOPY_SYMBOLS if s["sub_category"] == sub_category]


def search_dukascopy_symbols(query: str) -> List[Dict[str, Any]]:
    """銘柄を検索"""
    query_lower = query.lower()
    return [
        s for s in DUKASCOPY_SYMBOLS
        if query_lower in s["id"].lower()
        or query_lower in s["name"].lower()
        or query_lower in s["name_en"].lower()
    ]


def get_dukascopy_const_name(symbol_id: str) -> Optional[str]:
    """銘柄IDからDukascopy定数名を取得"""
    symbol = get_dukascopy_symbol_by_id(symbol_id)
    return symbol["dukascopy_const"] if symbol else None
