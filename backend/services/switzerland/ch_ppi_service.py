"""
スイスPPI（生産者・輸入物価指数）サービス
BFS（スイス連邦統計局）DAM APIからスイスPPIデータを取得

指標:
- Produzenten- und Importpreisindex (PPI/IPI)
- Preisindex des Gesamtangebots (PGA)
- 前年比 (YoY)
- 前月比 (MoM)

データソース:
- BFS DAM API: Produzenten- und Importpreisindex
- Asset ID: 36390908

発表スケジュール:
- 毎月中旬（BFS発表）
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
DATA_CACHE_FILE = CACHE_DIR / "ch_ppi_cache.json"


class ChPPIService:
    """スイスPPIサービス（BFS APIベース）"""

    DATA_CACHE_KEY = "switzerland:ch_ppi:data"
    ECONALPHA_ID = "ch_ppi"
    FMP_COUNTRY = "CH"
    FMP_EVENT_PATTERN = "Producer Price Index YoY"

    # BFS DAM API URL
    # Produzenten- und Importpreisindex, Preisindex des Gesamtangebots (PGA)
    BFS_ASSET_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/36390908/master"

    # Excel内の列インデックス（0-indexed）
    # 注意: BFSは指数の基準改定ごとに新しい基準列（例 "Dez 2025 = 100"）を挿入し
    #       % Vormonat / % Vorjahr 列が右にずれる。固定インデックスは破綻するため
    #       ヘッダー行のラベルから動的に列を解決する（下記は解決失敗時のフォールバック）。
    # Header row labels: "Datum"=日付, "% Vormonat"=MoM, "% Vorjahr"=YoY
    HEADER_ROW = 6
    DATA_START_ROW = 7
    COL_DATE = 2
    COL_MOM = 12
    COL_YOY = 13

    @classmethod
    def _resolve_columns(cls, df) -> Dict[str, int]:
        """ヘッダー行のラベルから日付/MoM/YoY列を動的解決（挿入列でのズレ対策）"""
        cols = {"date": cls.COL_DATE, "mom": cls.COL_MOM, "yoy": cls.COL_YOY}
        try:
            header = df.iloc[cls.HEADER_ROW]
            for c in range(df.shape[1]):
                label = header.iloc[c]
                if not isinstance(label, str):
                    continue
                norm = label.strip().lower()
                if norm == "datum":
                    cols["date"] = c
                elif norm == "% vormonat":
                    cols["mom"] = c
                elif norm == "% vorjahr":
                    cols["yoy"] = c
        except Exception as e:
            print(f"[ChPPI] Column resolve failed, using defaults: {e}")
        return cols

    def __init__(self):
        pass

    def get_ch_ppi_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """スイスPPIデータを取得"""
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
            # 最新値を取得
            latest = bfs_result[-1] if bfs_result else None

            cache_payload = {
                "data": bfs_result,
                "latest": latest,
                "metadata": {
                    "source": "Swiss Federal Statistical Office (BFS)",
                    "indicator": "Producer and Import Price Index",
                    "description": "スイス生産者・輸入物価指数（PPI）",
                    "asset_id": "36390908",
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
            print(f"[ChPPI] Fetching data from BFS API: {self.BFS_ASSET_URL}")

            # Excelファイルをダウンロード (公表ごとに damId が変わるため最新版を動的解決)
            from services.switzerland.bfs_asset_resolver import resolve_master_url_from_url
            resp = requests.get(resolve_master_url_from_url(self.BFS_ASSET_URL), timeout=60)
            resp.raise_for_status()

            # Excelファイルを読み込み
            excel_data = io.BytesIO(resp.content)

            # INDEX_m シートを読み込み（月次データ）
            df = pd.read_excel(excel_data, sheet_name='INDEX_m', header=None)

            # ヘッダーラベルから列を動的解決（基準改定の挿入列でのズレ対策）
            cols = self._resolve_columns(df)
            print(f"[ChPPI] Resolved columns: {cols}")

            result = []
            current_date = datetime.now(JST).date()

            for i in range(self.DATA_START_ROW, len(df)):
                date_val = df.iloc[i, cols["date"]]
                mom_val = df.iloc[i, cols["mom"]]
                yoy_val = df.iloc[i, cols["yoy"]]

                # 日付が有効かチェック
                if not isinstance(date_val, datetime):
                    continue

                # 未来のデータはスキップ
                if date_val.date() > current_date:
                    continue

                # 値が '...' の場合はスキップ
                if mom_val == '...' or yoy_val == '...':
                    continue

                date_str = date_val.strftime('%Y-%m-01')

                # 値を数値に変換
                def parse_value(val):
                    if pd.isna(val):
                        return None
                    if isinstance(val, str) and val.strip() in ['...', '', '-']:
                        return None
                    try:
                        return round(float(val), 2)
                    except (ValueError, TypeError):
                        return None

                ppi_yoy = parse_value(yoy_val)
                ppi_mom = parse_value(mom_val)

                # 少なくとも1つの値があれば追加
                if ppi_yoy is not None or ppi_mom is not None:
                    result.append({
                        "date": date_str,
                        "ppi_yoy": ppi_yoy,
                        "ppi_mom": ppi_mom,
                    })

            # 日付でソート
            result.sort(key=lambda x: x["date"])

            print(f"[ChPPI] Loaded {len(result)} records from BFS API")
            if result:
                print(f"[ChPPI] Date range: {result[0]['date']} to {result[-1]['date']}")
                print(f"[ChPPI] Latest: YoY={result[-1].get('ppi_yoy')}, MoM={result[-1].get('ppi_mom')}")

            return result

        except Exception as e:
            print(f"[ChPPI] Error loading from BFS API: {e}")
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
            print(f"[ChPPI] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュを保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ChPPI] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュを無効化"""
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態を取得"""
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "Swiss PPI",
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
ch_ppi_service = ChPPIService()
