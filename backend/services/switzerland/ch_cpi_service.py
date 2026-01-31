"""
スイスCPI（消費者物価指数）サービス
BFS（スイス連邦統計局）PxWeb APIからスイスCPIデータを取得

指標:
- CPI Total (消費者物価指数 総合)
- Kerninflation 1 (コアインフレ1: 生鮮食品・エネルギー除く)
- Kerninflation 2 (コアインフレ2: 生鮮食品・季節品・エネルギー除く)
- Inflation Rate YoY (前年比)
- Inflation Rate MoM (前月比)

データソース:
- BFS DAM API: LIK (Dezember 2020=100) 詳細データ
- Asset ID: 36366707

発表スケジュール:
- 毎月初旬（BFS発表）
- 発表時刻: 08:30 チューリッヒ時間

キャッシュ方式: FMP発表日時ベース判定方式
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
from services.switzerland.fmp_next_release_utils import (
    get_next_release_by_pattern,
    should_refresh_by_pattern,
)


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "switzerland" / "inflation"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "ch_cpi_cache.json"


class ChCPIService:
    """スイスCPIサービス（BFS APIベース）"""

    DATA_CACHE_KEY = "switzerland:ch_cpi:data"
    ECONALPHA_ID = "ch_cpi"
    FMP_COUNTRY = "CH"
    FMP_EVENT_PATTERN = "Inflation Rate YoY"

    # BFS DAM API URL
    # LIK (Dezember 2020=100), Detailresultate seit 1982
    BFS_ASSET_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/36366707/master"

    # Excel内の行インデックス（0-indexed）
    # Row 3: 日付ヘッダー
    # Row 4: Total
    # Row 476: Kerninflation 1
    # Row 480: Kerninflation 2
    HEADER_ROW = 3
    DATA_START_COL = 7  # Column H (0-indexed = 7)

    ROW_TOTAL = 4
    ROW_CORE1 = 476
    ROW_CORE2 = 480

    def __init__(self):
        pass

    def get_ch_cpi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """スイスCPIデータを取得"""
        # 次回発表日を取得
        next_release = get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY)

        # Redisキャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                last_updated_str = cached_data.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
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
            # 最新値を取得（実績データのみ - 2025年1月まで）
            latest = bfs_result[-1] if bfs_result else None

            cache_payload = {
                "data": bfs_result,
                "latest": latest,
                "metadata": {
                    "source": "Swiss Federal Statistical Office (BFS)",
                    "indicator": "Consumer Price Index",
                    "description": "スイス消費者物価指数（CPI）",
                    "base_year": "Dec 2020 = 100",
                    "asset_id": "36366707",
                },
                "last_updated": datetime.now(JST).isoformat(),
            }
            redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
            self._save_file_cache(cache_payload)

            return {
                "data": bfs_result,
                "latest": latest,
                "metadata": cache_payload["metadata"],
                "next_release": next_release,
                "cached": False,
                "source": "bfs_api",
                "last_updated": datetime.now(JST).isoformat(),
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
        """BFS DAM APIからデータを取得"""
        try:
            print(f"[ChCPI] Fetching data from BFS API: {self.BFS_ASSET_URL}")

            # Excelファイルをダウンロード
            resp = requests.get(self.BFS_ASSET_URL, timeout=60)
            resp.raise_for_status()

            # Excelファイルを読み込み
            excel_data = io.BytesIO(resp.content)

            # YoY（前年比）シートを読み込み
            df_yoy = pd.read_excel(excel_data, sheet_name='VAR_m-12', header=None)

            # MoM（前月比）シートを読み込み
            excel_data.seek(0)
            df_mom = pd.read_excel(excel_data, sheet_name='VAR_m-1', header=None)

            # 日付列を取得（Row 3, Column 7以降）
            dates = df_yoy.iloc[self.HEADER_ROW, self.DATA_START_COL:].tolist()

            # 各系列のデータを取得
            total_yoy = df_yoy.iloc[self.ROW_TOTAL, self.DATA_START_COL:].tolist()
            core1_yoy = df_yoy.iloc[self.ROW_CORE1, self.DATA_START_COL:].tolist()
            core2_yoy = df_yoy.iloc[self.ROW_CORE2, self.DATA_START_COL:].tolist()

            total_mom = df_mom.iloc[self.ROW_TOTAL, self.DATA_START_COL:].tolist()
            core1_mom = df_mom.iloc[self.ROW_CORE1, self.DATA_START_COL:].tolist()
            core2_mom = df_mom.iloc[self.ROW_CORE2, self.DATA_START_COL:].tolist()

            # データを構築
            result = []
            current_date = datetime.now(JST).date()

            for i, date_val in enumerate(dates):
                if pd.isna(date_val):
                    continue

                # datetime型に変換
                if isinstance(date_val, datetime):
                    date_obj = date_val
                else:
                    continue

                # 未来のデータ（予測値）はスキップ - 現在月より後のデータは除外
                # ただし、データが実績かどうかは難しいため、現在月の1ヶ月後までは含める
                if date_obj.date() > current_date:
                    continue

                date_str = date_obj.strftime('%Y-%m-01')

                # 値を取得（'...'や空白はNone）
                def parse_value(val):
                    if pd.isna(val):
                        return None
                    if isinstance(val, str) and val.strip() in ['...', '', '-']:
                        return None
                    try:
                        return round(float(val), 2)
                    except (ValueError, TypeError):
                        return None

                record = {
                    "date": date_str,
                    "cpi_yoy": parse_value(total_yoy[i]),
                    "cpi_mom": parse_value(total_mom[i]),
                    "core1_yoy": parse_value(core1_yoy[i]),
                    "core1_mom": parse_value(core1_mom[i]),
                    "core2_yoy": parse_value(core2_yoy[i]),
                    "core2_mom": parse_value(core2_mom[i]),
                }

                # 少なくとも1つの値があれば追加
                if any(v is not None for v in [
                    record["cpi_yoy"], record["cpi_mom"],
                    record["core1_yoy"], record["core1_mom"],
                    record["core2_yoy"], record["core2_mom"]
                ]):
                    result.append(record)

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"[ChCPI] Loaded {len(result)} records from BFS API")
            if result:
                print(f"[ChCPI] Date range: {result[0]['date']} to {result[-1]['date']}")
                print(f"[ChCPI] Latest: YoY={result[-1].get('cpi_yoy')}, MoM={result[-1].get('cpi_mom')}")

            return result

        except Exception as e:
            print(f"[ChCPI] Error loading from BFS API: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきかどうかを判定（FMP発表日ベース）"""
        return should_refresh_by_pattern(
            self.FMP_EVENT_PATTERN,
            last_updated_str,
            country=self.FMP_COUNTRY
        )

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        """ファイルキャッシュを読み込む"""
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ChCPI] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ChCPI] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Swiss CPI",
            "source": "Swiss Federal Statistical Office (BFS)",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": len(cached_data.get("data", [])) if cached_data else 0,
            "latest": cached_data.get("latest") if cached_data else None,
            "next_release": get_next_release_by_pattern(self.FMP_EVENT_PATTERN, country=self.FMP_COUNTRY),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
ch_cpi_service = ChCPIService()
