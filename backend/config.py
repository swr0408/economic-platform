"""
アプリ全体で共有する設定・定数を定義します。
"""

from pathlib import Path
import os
from typing import Dict, List

# CORS 許可オリジン
ALLOWED_ORIGINS: List[str] = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
]

# Seasonality データディレクトリ
_root = os.getenv("SEASONALITY_DIR")
SEASONALITY_DIR: Path = Path(_root) if _root else Path(__file__).parent.parent / "data" / "seasonality"

# Seasonality 統計JSON出力ディレクトリ（手動更新）
SEASONALITY_STATS_DIR: Path = (
    Path(__file__).parent / "data" / "manual_update" / "seasonality" / "output"
)

# Screenshots データディレクトリ
_screenshot_root = os.getenv("SCREENSHOT_DIR")
SCREENSHOT_DIR: Path = Path(_screenshot_root) if _screenshot_root else Path(__file__).parent.parent / "screenshots"

# Seasonality 画像として扱う拡張子
IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")

# アセットカテゴリ定義（通貨インデックスを追加）
ASSET_CATEGORIES: Dict[str, Dict] = {
    "interest_rates": {
        "name": "金利",
        "symbols": [
            "US10Y", 
            "US02Y", 
            "US30Y"
            ],
    },
    "equities": {
        "name": "株式",
        "symbols": [
            "S&P500",
            "ダウ平均",
            "ドル建て日経平均",
            "ナスダック100",
            "ハンセン指数",
            "ラッセル2000",
            "日経平均",
            "VIX",
            "SOX",
            "TOPIX",
        ],
    },
    "commodities": {
        "name": "商品",
        "symbols": [
            "シルバー",
            "ドル建てゴールド",
            "ブレント原油",
            "WTI原油",
            "天然ガス",
            "銅",
        ],
    },
    "fx": {
        "name": "為替",
        "subcategories": {
            "usd_straight": {
                "name": "ドルストレート",
                "symbols": [
                    "EURUSD",
                    "GBPUSD",
                    "AUDUSD",
                    "NZDUSD",
                    "USDCAD",
                    "USDCHF",
                ],
            },
            "cross_yen": {
                "name": "クロス円",
                "symbols": [
                    "USDJPY",
                    "EURJPY",
                    "GBPJPY",
                    "AUDJPY",
                    "NZDJPY",
                    "CADJPY",
                    "CHFJPY",
                ],
            },
            "synthetic": {
                "name": "合成通貨",
                "symbols": [
                    "AUDCAD",
                    "AUDCHF",
                    "AUDNZD",
                    "CADCHF",
                    "EURAUD",
                    "EURCAD",
                    "EURCHF",
                    "EURGBP",
                    "EURNZD",
                    "GBPAUD",
                    "GBPCAD",
                    "GBPCHF",
                    "GBPNZD",
                    "NZDCAD",
                    "NZDCHF",
                ],
            },
        },
    },
    "currency_index": {
        "name": "通貨インデックス",
        "symbols": [
            "USD_INDEX",
            "JPY_INDEX",
            "EUR_INDEX",
            "GBP_INDEX",
            "AUD_INDEX",
            "NZD_INDEX",
            "CAD_INDEX",
            "CHF_INDEX",
        ],
    },
}
