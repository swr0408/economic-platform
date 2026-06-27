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
- BFS DAM API: LIK (Dezember 2025=100) 詳細データ
- Seed Asset ID: 36669838 (orderNr su-i-05.02.66)
  ※ BFSは基準改定・月次公表ごとに新damIdを発番するため固定IDだと凍結する。
    bfs_asset_resolver で orderNr から最新版に動的解決し、行/列はラベル検出する。

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

    # BFS DAM API URL（シードID。resolverで同一orderNrの最新版に解決する）
    # LIK (Dezember 2025=100), Detailresultate seit 1982
    BFS_ASSET_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/36669838/master"

    # 行/列はラベル・コードで動的検出する（基準改定でレイアウトが変わるため）。
    # 検出失敗時のフォールバック既定値（旧 Dezember 2020=100 テーブル相当）。
    HEADER_ROW = 3
    DATA_START_COL = 7

    ROW_TOTAL = 4
    ROW_CORE1 = 476
    ROW_CORE2 = 480

    # ラベル/コード検出キー
    CODE_TOTAL = "100_100"
    LABEL_TOTAL = "Total"
    LABEL_CORE1 = "Kerninflation 1"
    LABEL_CORE2 = "Kerninflation 2"

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
                    "base_year": "Dec 2025 = 100",
                    "asset_id": "36669838 (orderNr su-i-05.02.66, dynamic)",
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

    @staticmethod
    def _parse_value(val) -> Optional[float]:
        """セル値を数値に（'...'/空白/'-'はNone）"""
        if pd.isna(val):
            return None
        if isinstance(val, str) and val.strip() in ['...', '', '-']:
            return None
        try:
            return round(float(val), 2)
        except (ValueError, TypeError):
            return None

    def _locate(self, df: "pd.DataFrame") -> Dict[str, int]:
        """Excelのヘッダー行・日付開始列・各系列の行をラベル/コードで動的検出。

        BFSは基準改定で列数（多言語ラベル列）や行位置が変わるため、固定インデックス
        は脆い。検出失敗時はフォールバック既定値を用いる。
        """
        # ヘッダー行: 先頭8行でTimestampを最も多く含む行
        header_row = self.HEADER_ROW
        for i in range(min(8, df.shape[0])):
            cnt = sum(isinstance(v, (datetime, pd.Timestamp)) for v in df.iloc[i].tolist())
            if cnt >= 12:
                header_row = i
                break

        # 日付開始列: ヘッダー行で最初にTimestampが現れる列
        first_col = self.DATA_START_COL
        hdr = df.iloc[header_row].tolist()
        for c, v in enumerate(hdr):
            if isinstance(v, (datetime, pd.Timestamp)):
                first_col = c
                break

        # Total行: コード(列0)が CODE_TOTAL、無ければラベル一致
        row_total = None
        for i in range(df.shape[0]):
            if str(df.iloc[i, 0]).strip() == self.CODE_TOTAL:
                row_total = i
                break
        if row_total is None:
            row_total = self._find_row_by_label(df, self.LABEL_TOTAL, first_col, exact=True)
        if row_total is None:
            row_total = self.ROW_TOTAL

        row_core1 = self._find_row_by_label(df, self.LABEL_CORE1, first_col)
        row_core2 = self._find_row_by_label(df, self.LABEL_CORE2, first_col)
        if row_core1 is None:
            row_core1 = self.ROW_CORE1
        if row_core2 is None:
            row_core2 = self.ROW_CORE2

        return {
            "header_row": header_row,
            "first_col": first_col,
            "total": row_total,
            "core1": row_core1,
            "core2": row_core2,
        }

    def _find_row_by_label(self, df: "pd.DataFrame", needle: str,
                           label_cols_end: int, exact: bool = False) -> Optional[int]:
        """ラベル列（日付列より手前）から needle に一致する最初の行を返す"""
        end = max(1, min(label_cols_end, df.shape[1]))
        for i in range(df.shape[0]):
            for c in range(0, end):
                cell = str(df.iloc[i, c]).strip()
                if (cell == needle) if exact else (needle in cell):
                    return i
        return None

    def _extract_sheet(self, df: "pd.DataFrame") -> Dict[str, Dict[str, Optional[float]]]:
        """1シートから {date_str: {total, core1, core2}} を抽出"""
        loc = self._locate(df)
        out: Dict[str, Dict[str, Optional[float]]] = {}
        hdr = df.iloc[loc["header_row"]].tolist()
        for c in range(loc["first_col"], df.shape[1]):
            date_val = hdr[c] if c < len(hdr) else None
            if not isinstance(date_val, (datetime, pd.Timestamp)):
                continue
            date_str = date_val.strftime('%Y-%m-01')
            out[date_str] = {
                "total": self._parse_value(df.iloc[loc["total"], c]),
                "core1": self._parse_value(df.iloc[loc["core1"], c]),
                "core2": self._parse_value(df.iloc[loc["core2"], c]),
            }
        return out

    def _load_from_bfs(self) -> List[Dict[str, Any]]:
        """BFS DAM APIからデータを取得（orderNrで最新版に動的解決）"""
        try:
            from services.switzerland.bfs_asset_resolver import resolve_master_url_from_url
            url = resolve_master_url_from_url(self.BFS_ASSET_URL)
            print(f"[ChCPI] Fetching data from BFS API: {url}")

            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            content = resp.content

            # YoY（前年比）/ MoM（前月比）シート
            df_yoy = pd.read_excel(io.BytesIO(content), sheet_name='VAR_m-12', header=None)
            df_mom = pd.read_excel(io.BytesIO(content), sheet_name='VAR_m-1', header=None)

            yoy = self._extract_sheet(df_yoy)
            mom = self._extract_sheet(df_mom)

            current_date = datetime.now(JST).date()
            result = []
            for date_str in sorted(set(yoy) | set(mom)):
                # 未来月（予測）は除外
                if datetime.strptime(date_str, '%Y-%m-%d').date() > current_date:
                    continue
                y = yoy.get(date_str, {})
                m = mom.get(date_str, {})
                record = {
                    "date": date_str,
                    "cpi_yoy": y.get("total"),
                    "cpi_mom": m.get("total"),
                    "core1_yoy": y.get("core1"),
                    "core1_mom": m.get("core1"),
                    "core2_yoy": y.get("core2"),
                    "core2_mom": m.get("core2"),
                }
                if any(v is not None for v in record.values() if not isinstance(v, str)):
                    result.append(record)

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
