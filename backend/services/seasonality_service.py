"""
Seasonality 機能に関するドメインロジック（ファイル走査・分類）を集約します。
"""

from pathlib import Path
from typing import Dict, List, Optional
import time

try:
    from backend.config import SEASONALITY_DIR, SEASONALITY_STATS_DIR, ASSET_CATEGORIES, IMG_EXTS
except ImportError:
    from config import SEASONALITY_DIR, SEASONALITY_STATS_DIR, ASSET_CATEGORIES, IMG_EXTS


# インデックスキャッシュ（元データは手動更新のみのため24時間TTL）
_index_cache: Optional[Dict] = None
_cache_timestamp: float = 0
_CACHE_TTL: float = 86400  # 24時間


def get_symbol_category(symbol: str) -> Dict[str, Optional[str]]:
    """シンボルが属するカテゴリ/サブカテゴリを返す。"""
    for category_id, category in ASSET_CATEGORIES.items():
        if "symbols" in category and symbol in category["symbols"]:
            return {"category": category_id, "subcategory": None}
        elif "subcategories" in category:
            for sub_id, sub in category["subcategories"].items():
                if symbol in sub["symbols"]:
                    return {"category": category_id, "subcategory": sub_id}
    return {"category": "other", "subcategory": None}


def list_images(dirpath: Path) -> List[Dict[str, str]]:
    """指定ディレクトリ直下の画像ファイルを列挙し、表示用URLを含む辞書の配列を返す。"""
    if not dirpath.exists():
        return []
    rows: List[Dict[str, str]] = []
    for p in sorted(dirpath.iterdir()):
        if p.is_file() and p.suffix.lower() in IMG_EXTS:
            rel = p.parent.relative_to(SEASONALITY_DIR).as_posix()
            rows.append({"name": p.name, "url": f"/static/seasonality/{rel}/{p.name}"})
    return rows



def get_first_image(dirpath: Path) -> Optional[str]:
    """指定ディレクトリから最初の画像URLを取得する（高速版）。"""
    if not dirpath.exists():
        return None
    for p in sorted(dirpath.iterdir()):
        if p.is_file() and p.suffix.lower() in IMG_EXTS:
            rel = p.parent.relative_to(SEASONALITY_DIR).as_posix()
            return f"/static/seasonality/{rel}/{p.name}"
    return None


def build_index() -> Dict[str, Dict]:
    """カテゴリ別の銘柄インデックスを構築して返す（キャッシュ付き）。"""
    global _index_cache, _cache_timestamp

    # キャッシュが有効な場合はそれを返す
    current_time = time.time()
    if _index_cache is not None and (current_time - _cache_timestamp) < _CACHE_TTL:
        return _index_cache

    all_items = []

    if not SEASONALITY_DIR.exists():
        return {"categories": {}}

    for sym_dir in sorted(SEASONALITY_DIR.iterdir()):
        if not sym_dir.is_dir():
            continue
        symbol = sym_dir.name

        cover = get_first_image(sym_dir / "seasonality_charts")
        has_stats = (SEASONALITY_STATS_DIR / symbol / "monthly_stats.json").exists()
        if not cover and not has_stats:
            continue

        category_info = get_symbol_category(symbol)

        all_items.append(
            {
                "symbol": symbol,
                "coverUrl": cover,
                "category": category_info["category"],
                "subcategory": category_info["subcategory"],
            }
        )

    # カテゴリ枠組みを作成
    categorized: Dict[str, Dict] = {}
    for cat_id, cat_data in ASSET_CATEGORIES.items():
        categorized[cat_id] = {"name": cat_data["name"], "items": [], "subcategories": {}}
        if "subcategories" in cat_data:
            for sub_id, sub_data in cat_data["subcategories"].items():
                categorized[cat_id]["subcategories"][sub_id] = {"name": sub_data["name"], "items": []}

    # その他カテゴリ
    categorized["other"] = {"name": "その他", "items": [], "subcategories": {}}

    # 銘柄をカテゴリへ振り分け
    for item in all_items:
        cat = item["category"]
        sub = item["subcategory"]
        if cat in categorized and sub and sub in categorized[cat]["subcategories"]:
            categorized[cat]["subcategories"][sub]["items"].append(item)
        elif cat in categorized:
            categorized[cat]["items"].append(item)
        else:
            categorized["other"]["items"].append(item)

    # キャッシュに保存
    result = {"categories": categorized}
    _index_cache = result
    _cache_timestamp = current_time

    return result


def build_manifest(symbol: str) -> Dict:
    """指定シンボルフォルダ内の画像群をマニフェスト形式で返す。"""
    sym_dir = SEASONALITY_DIR / symbol
    seasonality = list_images(sym_dir / "seasonality_charts")

    return {
        "symbol": symbol,
        "seasonalityCharts": seasonality,
    }
