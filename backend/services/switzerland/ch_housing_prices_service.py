"""
スイス住宅価格指数サービス
BFS（スイス連邦統計局）DAM APIから住宅価格指数データを取得

指標:
- 住宅価格指数 Total (Wohneigentum Total)
- 前期比 (QoQ)
- 前年比 (YoY)

データソース:
- BFS DAM API: 住宅価格指数
- Asset ID: 36412305

発表スケジュール:
- 四半期（BFS発表）
- RSS: https://www.bfs.admin.ch/bfs/en/home/aktuell/agenda/jcr:content/root/main/agendatopic.rss.agendaTopic.xml

キャッシュ方式: RSS発表日時ベース判定方式
"""
import json
import io
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import requests
import pandas as pd

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")
ZURICH = ZoneInfo("Europe/Zurich")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "housing"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ch_housing_prices_cache.json"


def get_bfs_next_release_from_rss(keyword: str = "Immobilienpreisindex") -> Optional[str]:
    """BFS RSSフィードから次回発表日を取得

    Args:
        keyword: RSSアイテムのタイトルに含まれるキーワード

    Returns:
        次回発表日時文字列 (YYYY-MM-DD HH:MM) or None
    """
    try:
        rss_url = "https://www.bfs.admin.ch/bfs/en/home/aktuell/agenda/jcr:content/root/main/agendatopic.rss.agendaTopic.xml"
        resp = requests.get(rss_url, timeout=30)
        resp.raise_for_status()

        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.content)

        now = datetime.now(ZURICH)

        for item in root.findall(".//item"):
            title = item.find("title")
            pub_date = item.find("pubDate")

            if title is not None and keyword.lower() in title.text.lower():
                if pub_date is not None:
                    # RFC 2822形式をパース
                    from email.utils import parsedate_to_datetime
                    try:
                        release_dt = parsedate_to_datetime(pub_date.text)
                        release_dt = release_dt.astimezone(ZURICH)

                        # 未来の日付のみ
                        if release_dt > now:
                            return release_dt.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        pass

        return None
    except Exception as e:
        print(f"[CHHousingPrices] Error fetching RSS: {e}")
        return None


class ChHousingPricesService:
    """スイス住宅価格指数サービス（BFS APIベース）"""

    DATA_CACHE_KEY = "switzerland:ch_housing_prices:data"

    # BFS DAM API URL
    # 住宅価格指数 (Immobilienpreisindex)
    BFS_ASSET_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/36412305/master"

    def __init__(self):
        pass

    def get_housing_prices_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """スイス住宅価格指数データを取得"""
        # 次回発表日を取得（RSSから）
        next_release = get_bfs_next_release_from_rss("Immobilienpreisindex")

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str, next_release):
                    return {
                        "data": cached_data.get("data", []),
                        "latest": cached_data.get("latest"),
                        "metadata": cached_data.get("metadata", {}),
                        "next_release": next_release,
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # BFS APIから取得
        bfs_result = self._load_from_bfs()
        if bfs_result:
            latest = bfs_result[-1] if bfs_result else None

            from services.usa.fmp_next_release_utils import guarded_last_updated
            now_str = datetime.now(JST).isoformat()
            last_updated = guarded_last_updated(
                self.DATA_CACHE_KEY, latest.get("date") if latest else None, now_str
            )
            cache_payload = {
                "data": bfs_result,
                "latest": latest,
                "metadata": {
                    "source": "Swiss Federal Statistical Office (BFS)",
                    "indicator": "Housing Price Index",
                    "description": "スイス住宅価格指数",
                    "unit": "index (2020Q1=100)",
                    "frequency": "quarterly",
                },
                "last_updated": last_updated,
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": bfs_result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "api",
                "last_updated": last_updated,
            }

        # ファイルキャッシュフォールバック
        file_cache = self._load_file_cache()
        if file_cache:
            return {
                "data": file_cache.get("data", []),
                "latest": file_cache.get("latest"),
                "metadata": file_cache.get("metadata", {}),
                "next_release": next_release,
                "cached": True,
                "source": "file (fallback)",
                "last_updated": file_cache.get("last_updated"),
            }

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "next_release": next_release,
            "cached": False,
            "source": "none",
            "last_updated": None,
            "error": "No data available",
        }

    def _load_from_bfs(self) -> List[Dict[str, Any]]:
        """BFS DAM APIからExcelデータを取得してパース"""
        try:
            print(f"[CHHousingPrices] Fetching data from: {self.BFS_ASSET_URL}")

            from services.switzerland.bfs_asset_resolver import resolve_master_url_from_url
            resp = requests.get(resolve_master_url_from_url(self.BFS_ASSET_URL), timeout=60)
            resp.raise_for_status()

            # Excelを解析
            excel_data = io.BytesIO(resp.content)

            # シート名を確認
            xl = pd.ExcelFile(excel_data)
            print(f"[CHHousingPrices] Sheet names: {xl.sheet_names}")

            # データを読み込み（最初のシートを試す）
            df = pd.read_excel(excel_data, sheet_name=0, header=None)
            print(f"[CHHousingPrices] DataFrame shape: {df.shape}")
            print(f"[CHHousingPrices] First 10 rows:\n{df.head(10)}")

            # "Wohneigentum Total" または "Total" を含む行を探す
            result = self._parse_housing_price_data(df)

            if result:
                print(f"[CHHousingPrices] Loaded {len(result)} records")
                if result:
                    print(f"[CHHousingPrices] Date range: {result[0]['date']} to {result[-1]['date']}")
                    print(f"[CHHousingPrices] Latest value: {result[-1].get('value')}")

            return result

        except Exception as e:
            print(f"[CHHousingPrices] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_housing_price_data(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Excelデータから住宅価格指数を抽出

        BFSの住宅価格指数Excelは以下の構造:
        - 行11以降にデータ
        - 列0: 四半期名 (Q1 2017, Q2 2017, ...)
        - 列1: Total の値
        """
        result = []

        try:
            # データ行を探す: 列0に "Q1 2017" のようなパターンがある行
            for idx, row in df.iterrows():
                first_cell = row.iloc[0]
                if pd.isna(first_cell):
                    continue

                first_cell_str = str(first_cell).strip()

                # "Q1 2017", "Q2 2020" などのパターンをチェック
                # 形式: "Qn YYYY" (スペース区切り)
                if first_cell_str.startswith("Q") and " " in first_cell_str:
                    parts = first_cell_str.split()
                    if len(parts) == 2:
                        q_part = parts[0]  # "Q1", "Q2", etc.
                        year_part = parts[1]  # "2017", "2020", etc.

                        try:
                            q = int(q_part[1])  # "Q1" -> 1
                            year = int(year_part)
                            month = (q - 1) * 3 + 1
                            date_str = f"{year}-{month:02d}-01"
                            quarter_str = f"{year}Q{q}"

                            # 列1 (Total) の値を取得
                            value = row.iloc[1]
                            if pd.notna(value):
                                result.append({
                                    "date": date_str,
                                    "quarter": quarter_str,
                                    "value": round(float(value), 2),
                                })
                        except (ValueError, IndexError) as e:
                            print(f"[CHHousingPrices] Error parsing row {idx}: {e}")
                            continue

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            # QoQ/YoYを計算
            result = self._calculate_changes(result)

            print(f"[CHHousingPrices] Parsed {len(result)} records")
            return result

        except Exception as e:
            print(f"[CHHousingPrices] Error parsing data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _calculate_changes(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """QoQ（前期比）とYoY（前年比）を計算"""
        if not data:
            return data

        quarter_map = {item["quarter"]: i for i, item in enumerate(data)}

        for i, item in enumerate(data):
            quarter = item["quarter"]
            value = item["value"]

            # QoQ: 前期比（%変化）
            qoq = None
            if i > 0:
                prev_value = data[i - 1]["value"]
                if prev_value and prev_value != 0:
                    qoq = round((value - prev_value) / prev_value * 100, 2)

            # YoY: 前年比（%変化）
            yoy = None
            try:
                year = int(quarter[:4])
                q = quarter[-1]
                prev_year_quarter = f"{year - 1}Q{q}"
                if prev_year_quarter in quarter_map:
                    prev_year_idx = quarter_map[prev_year_quarter]
                    prev_year_value = data[prev_year_idx]["value"]
                    if prev_year_value and prev_year_value != 0:
                        yoy = round((value - prev_year_value) / prev_year_value * 100, 2)
            except (ValueError, KeyError):
                pass

            item["qoq"] = qoq
            item["yoy"] = yoy

        return data

    def _should_refresh(self, last_updated_str: str, next_release_str: Optional[str]) -> bool:
        """キャッシュを更新すべきかどうかを判定"""
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(ZURICH)

            if next_release_str:
                try:
                    next_release = datetime.strptime(next_release_str, "%Y-%m-%d %H:%M")
                    next_release = next_release.replace(tzinfo=ZURICH)

                    if now > next_release and last_updated.astimezone(ZURICH) < next_release:
                        print(f"[CHHousingPrices] Data is stale, release was {next_release_str}")
                        return True
                except ValueError:
                    pass

            # 7日以上経過していたら更新
            if (now - last_updated.astimezone(ZURICH)).days >= 7:
                print("[CHHousingPrices] Cache is older than 7 days, refreshing")
                return True

            return False
        except Exception as e:
            print(f"[CHHousingPrices] Error checking refresh: {e}")
            return True

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CHHousingPrices] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CHHousingPrices] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        next_release = get_bfs_next_release_from_rss("Immobilienpreisindex")

        return {
            "indicator": "Swiss Housing Price Index",
            "source": "Swiss Federal Statistical Office (BFS)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": next_release,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ch_housing_prices_service = ChHousingPricesService()
