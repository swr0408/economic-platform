"""
銘柄マスターデータ定義

yfinance のティッカーシンボルと表示名のマッピング
カテゴリ: forex (為替), index (株価指数), commodity (商品), bond (債券), other (その他)
"""
from typing import Dict, List, Optional, TypedDict


class SymbolInfo(TypedDict):
    """銘柄情報"""
    id: str                    # 内部ID（スネークケース）
    ticker: str                # yfinance ティッカーシンボル
    name: str                  # 日本語名
    name_en: str               # 英語名
    category: str              # カテゴリ
    sub_category: Optional[str]  # サブカテゴリ


# =============================================================================
# 銘柄マスターデータ
# =============================================================================

MARKET_SYMBOLS: List[SymbolInfo] = [
    # =========================================================================
    # 為替 - ドルストレート
    # =========================================================================
    {"id": "usdjpy", "ticker": "USDJPY=X", "name": "ドル円", "name_en": "USD/JPY", "category": "forex", "sub_category": "usd"},
    {"id": "eurusd", "ticker": "EURUSD=X", "name": "ユーロドル", "name_en": "EUR/USD", "category": "forex", "sub_category": "usd"},
    {"id": "gbpusd", "ticker": "GBPUSD=X", "name": "ポンドドル", "name_en": "GBP/USD", "category": "forex", "sub_category": "usd"},
    {"id": "audusd", "ticker": "AUDUSD=X", "name": "豪ドル米ドル", "name_en": "AUD/USD", "category": "forex", "sub_category": "usd"},
    {"id": "nzdusd", "ticker": "NZDUSD=X", "name": "NZドル米ドル", "name_en": "NZD/USD", "category": "forex", "sub_category": "usd"},
    {"id": "usdcad", "ticker": "USDCAD=X", "name": "ドルカナダ", "name_en": "USD/CAD", "category": "forex", "sub_category": "usd"},
    {"id": "usdchf", "ticker": "USDCHF=X", "name": "ドルスイス", "name_en": "USD/CHF", "category": "forex", "sub_category": "usd"},

    # =========================================================================
    # 為替 - クロス円
    # =========================================================================
    {"id": "eurjpy", "ticker": "EURJPY=X", "name": "ユーロ円", "name_en": "EUR/JPY", "category": "forex", "sub_category": "jpy"},
    {"id": "gbpjpy", "ticker": "GBPJPY=X", "name": "ポンド円", "name_en": "GBP/JPY", "category": "forex", "sub_category": "jpy"},
    {"id": "audjpy", "ticker": "AUDJPY=X", "name": "豪ドル円", "name_en": "AUD/JPY", "category": "forex", "sub_category": "jpy"},
    {"id": "nzdjpy", "ticker": "NZDJPY=X", "name": "NZドル円", "name_en": "NZD/JPY", "category": "forex", "sub_category": "jpy"},
    {"id": "cadjpy", "ticker": "CADJPY=X", "name": "カナダ円", "name_en": "CAD/JPY", "category": "forex", "sub_category": "jpy"},
    {"id": "chfjpy", "ticker": "CHFJPY=X", "name": "スイス円", "name_en": "CHF/JPY", "category": "forex", "sub_category": "jpy"},

    # =========================================================================
    # 為替 - クロス（その他）
    # =========================================================================
    {"id": "eurgbp", "ticker": "EURGBP=X", "name": "ユーロポンド", "name_en": "EUR/GBP", "category": "forex", "sub_category": "cross"},
    {"id": "euraud", "ticker": "EURAUD=X", "name": "ユーロ豪ドル", "name_en": "EUR/AUD", "category": "forex", "sub_category": "cross"},
    {"id": "eurnzd", "ticker": "EURNZD=X", "name": "ユーロNZドル", "name_en": "EUR/NZD", "category": "forex", "sub_category": "cross"},
    {"id": "eurcad", "ticker": "EURCAD=X", "name": "ユーロカナダ", "name_en": "EUR/CAD", "category": "forex", "sub_category": "cross"},
    {"id": "eurchf", "ticker": "EURCHF=X", "name": "ユーロスイス", "name_en": "EUR/CHF", "category": "forex", "sub_category": "cross"},
    {"id": "gbpaud", "ticker": "GBPAUD=X", "name": "ポンド豪ドル", "name_en": "GBP/AUD", "category": "forex", "sub_category": "cross"},
    {"id": "gbpnzd", "ticker": "GBPNZD=X", "name": "ポンドNZドル", "name_en": "GBP/NZD", "category": "forex", "sub_category": "cross"},
    {"id": "gbpcad", "ticker": "GBPCAD=X", "name": "ポンドカナダ", "name_en": "GBP/CAD", "category": "forex", "sub_category": "cross"},
    {"id": "gbpchf", "ticker": "GBPCHF=X", "name": "ポンドスイス", "name_en": "GBP/CHF", "category": "forex", "sub_category": "cross"},
    {"id": "audnzd", "ticker": "AUDNZD=X", "name": "豪ドルNZドル", "name_en": "AUD/NZD", "category": "forex", "sub_category": "cross"},
    {"id": "audcad", "ticker": "AUDCAD=X", "name": "豪ドルカナダ", "name_en": "AUD/CAD", "category": "forex", "sub_category": "cross"},
    {"id": "audchf", "ticker": "AUDCHF=X", "name": "豪ドルスイス", "name_en": "AUD/CHF", "category": "forex", "sub_category": "cross"},
    {"id": "nzdcad", "ticker": "NZDCAD=X", "name": "NZドルカナダ", "name_en": "NZD/CAD", "category": "forex", "sub_category": "cross"},
    {"id": "nzdchf", "ticker": "NZDCHF=X", "name": "NZドルスイス", "name_en": "NZD/CHF", "category": "forex", "sub_category": "cross"},
    {"id": "cadchf", "ticker": "CADCHF=X", "name": "カナダスイス", "name_en": "CAD/CHF", "category": "forex", "sub_category": "cross"},

    # =========================================================================
    # 通貨インデックス
    # =========================================================================
    {"id": "dxy", "ticker": "DX-Y.NYB", "name": "ドルインデックス", "name_en": "USD Index (DXY)", "category": "forex", "sub_category": "index"},
    # 注: 他の通貨インデックス（EUR_INDEX等）はyfinanceで直接取得困難。計算で代替の可能性あり

    # =========================================================================
    # 株価指数 - 米国
    # =========================================================================
    {"id": "sp500", "ticker": "^GSPC", "name": "S&P500", "name_en": "S&P 500", "category": "index", "sub_category": "us"},
    {"id": "dow", "ticker": "^DJI", "name": "ダウ平均", "name_en": "Dow Jones", "category": "index", "sub_category": "us"},
    {"id": "nasdaq100", "ticker": "^NDX", "name": "ナスダック100", "name_en": "Nasdaq 100", "category": "index", "sub_category": "us"},
    {"id": "nasdaq", "ticker": "^IXIC", "name": "ナスダック総合", "name_en": "Nasdaq Composite", "category": "index", "sub_category": "us"},
    {"id": "russell2000", "ticker": "^RUT", "name": "ラッセル2000", "name_en": "Russell 2000", "category": "index", "sub_category": "us"},
    {"id": "sox", "ticker": "^SOX", "name": "フィラデルフィア半導体指数", "name_en": "SOX (Semiconductor)", "category": "index", "sub_category": "us"},
    {"id": "vix", "ticker": "^VIX", "name": "VIX（恐怖指数）", "name_en": "VIX", "category": "index", "sub_category": "us"},

    # =========================================================================
    # 株価指数 - 日本・アジア
    # =========================================================================
    {"id": "nikkei225", "ticker": "^N225", "name": "日経平均", "name_en": "Nikkei 225", "category": "index", "sub_category": "asia"},
    {"id": "topix", "ticker": "^TPX", "name": "TOPIX", "name_en": "TOPIX", "category": "index", "sub_category": "asia"},
    {"id": "hangseng", "ticker": "^HSI", "name": "ハンセン指数", "name_en": "Hang Seng", "category": "index", "sub_category": "asia"},

    # =========================================================================
    # 株価指数 - 欧州
    # =========================================================================
    {"id": "dax", "ticker": "^GDAXI", "name": "DAX", "name_en": "DAX", "category": "index", "sub_category": "europe"},
    {"id": "ftse100", "ticker": "^FTSE", "name": "FTSE100", "name_en": "FTSE 100", "category": "index", "sub_category": "europe"},
    {"id": "cac40", "ticker": "^FCHI", "name": "CAC40", "name_en": "CAC 40", "category": "index", "sub_category": "europe"},

    # =========================================================================
    # 債券利回り（米国）
    # =========================================================================
    {"id": "us02y", "ticker": "^IRX", "name": "米国2年債利回り", "name_en": "US 2Y Yield", "category": "bond", "sub_category": "us"},
    # 注: ^IRXは13週TB。2年債は別途データソースが必要な場合あり
    {"id": "us10y", "ticker": "^TNX", "name": "米国10年債利回り", "name_en": "US 10Y Yield", "category": "bond", "sub_category": "us"},
    {"id": "us30y", "ticker": "^TYX", "name": "米国30年債利回り", "name_en": "US 30Y Yield", "category": "bond", "sub_category": "us"},

    # =========================================================================
    # 商品 - 貴金属
    # =========================================================================
    {"id": "gold", "ticker": "GC=F", "name": "金（ドル建て）", "name_en": "Gold (USD)", "category": "commodity", "sub_category": "metal"},
    {"id": "silver", "ticker": "SI=F", "name": "銀（ドル建て）", "name_en": "Silver (USD)", "category": "commodity", "sub_category": "metal"},
    {"id": "copper", "ticker": "HG=F", "name": "銅", "name_en": "Copper", "category": "commodity", "sub_category": "metal"},

    # =========================================================================
    # 商品 - エネルギー
    # =========================================================================
    {"id": "crude_oil", "ticker": "CL=F", "name": "原油（WTI）", "name_en": "Crude Oil (WTI)", "category": "commodity", "sub_category": "energy"},
    {"id": "brent_oil", "ticker": "BZ=F", "name": "原油（ブレント）", "name_en": "Brent Crude", "category": "commodity", "sub_category": "energy"},
    {"id": "natural_gas", "ticker": "NG=F", "name": "天然ガス", "name_en": "Natural Gas", "category": "commodity", "sub_category": "energy"},

    # =========================================================================
    # ドル建て指数（計算値）
    # =========================================================================
    {"id": "nikkei_usd", "ticker": "^N225", "name": "日経平均（ドル建て）", "name_en": "Nikkei 225 (USD)", "category": "index", "sub_category": "calculated"},
    # 注: ドル建て日経はN225 / USDJPYで計算

    # =========================================================================
    # 各通貨建てゴールド（計算値）
    # =========================================================================
    {"id": "gold_jpy", "ticker": "GC=F", "name": "金（円建て）", "name_en": "Gold (JPY)", "category": "commodity", "sub_category": "calculated"},
    {"id": "gold_eur", "ticker": "GC=F", "name": "金（ユーロ建て）", "name_en": "Gold (EUR)", "category": "commodity", "sub_category": "calculated"},
    {"id": "gold_gbp", "ticker": "GC=F", "name": "金（ポンド建て）", "name_en": "Gold (GBP)", "category": "commodity", "sub_category": "calculated"},
    {"id": "gold_aud", "ticker": "GC=F", "name": "金（豪ドル建て）", "name_en": "Gold (AUD)", "category": "commodity", "sub_category": "calculated"},
    {"id": "gold_cad", "ticker": "GC=F", "name": "金（カナダドル建て）", "name_en": "Gold (CAD)", "category": "commodity", "sub_category": "calculated"},
    {"id": "gold_chf", "ticker": "GC=F", "name": "金（スイスフラン建て）", "name_en": "Gold (CHF)", "category": "commodity", "sub_category": "calculated"},
    {"id": "gold_nzd", "ticker": "GC=F", "name": "金（NZドル建て）", "name_en": "Gold (NZD)", "category": "commodity", "sub_category": "calculated"},
]


# =============================================================================
# カテゴリ定義
# =============================================================================

SYMBOL_CATEGORIES = {
    "forex": "為替",
    "index": "株価指数",
    "commodity": "商品",
    "bond": "債券",
}

SYMBOL_SUB_CATEGORIES = {
    # 為替
    "usd": "ドルストレート",
    "jpy": "クロス円",
    "cross": "その他クロス",
    "index": "通貨インデックス",
    # 株価指数
    "us": "米国",
    "asia": "日本・アジア",
    "europe": "欧州",
    # 商品
    "metal": "貴金属",
    "energy": "エネルギー",
    "calculated": "計算値",
}


# =============================================================================
# ヘルパー関数
# =============================================================================

def get_symbol_by_id(symbol_id: str) -> Optional[SymbolInfo]:
    """IDから銘柄情報を取得"""
    for symbol in MARKET_SYMBOLS:
        if symbol["id"] == symbol_id:
            return symbol
    return None


def get_symbols_by_category(category: str) -> List[SymbolInfo]:
    """カテゴリから銘柄リストを取得"""
    return [s for s in MARKET_SYMBOLS if s["category"] == category]


def get_symbols_by_sub_category(sub_category: str) -> List[SymbolInfo]:
    """サブカテゴリから銘柄リストを取得"""
    return [s for s in MARKET_SYMBOLS if s.get("sub_category") == sub_category]


def get_all_symbols() -> List[SymbolInfo]:
    """全銘柄リストを取得"""
    return MARKET_SYMBOLS.copy()


def get_ticker_by_id(symbol_id: str) -> Optional[str]:
    """IDからyfinanceティッカーを取得"""
    symbol = get_symbol_by_id(symbol_id)
    return symbol["ticker"] if symbol else None


def search_symbols(query: str) -> List[SymbolInfo]:
    """銘柄を検索"""
    query_lower = query.lower()
    return [
        s for s in MARKET_SYMBOLS
        if query_lower in s["name"].lower() or
           query_lower in s["name_en"].lower() or
           query_lower in s["id"].lower()
    ]


# 計算が必要な銘柄のマッピング（変換元 → 変換に必要な為替ペア）
CALCULATED_SYMBOLS: Dict[str, Dict[str, str]] = {
    "nikkei_usd": {"base": "nikkei225", "fx": "usdjpy", "operation": "divide"},
    "gold_jpy": {"base": "gold", "fx": "usdjpy", "operation": "multiply"},
    "gold_eur": {"base": "gold", "fx": "eurusd", "operation": "divide"},
    "gold_gbp": {"base": "gold", "fx": "gbpusd", "operation": "divide"},
    "gold_aud": {"base": "gold", "fx": "audusd", "operation": "divide"},
    "gold_cad": {"base": "gold", "fx": "usdcad", "operation": "multiply"},
    "gold_chf": {"base": "gold", "fx": "usdchf", "operation": "multiply"},
    "gold_nzd": {"base": "gold", "fx": "nzdusd", "operation": "divide"},
}


def is_calculated_symbol(symbol_id: str) -> bool:
    """計算が必要な銘柄かどうか"""
    return symbol_id in CALCULATED_SYMBOLS


def get_calculation_info(symbol_id: str) -> Optional[Dict[str, str]]:
    """計算情報を取得"""
    return CALCULATED_SYMBOLS.get(symbol_id)
