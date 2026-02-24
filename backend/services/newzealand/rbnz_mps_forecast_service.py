"""
RBNZ MPS (Monetary Policy Statement) 経済見通しサービス

データソース:
- RBNZ MPS Data Pack Excel（手動配置）
- backend/data/excel/mps---data.xlsx（ファイル名が更新のたびに置き換え）

指標（8シート）:
- i.1: OCRパス（今回 vs 前回）
- 2.15: ヘッドラインCPI / Non-tradables / Tradables
- 5.1: インフレ内訳（Headline/Non-tradables/Tradables × 今回/前回）
- 5.2: 民間セクターLCI賃金インフレ
- 2.10: Output gap
- 2.11: 失業率
- 6.4: OCR & 中立OCR指標スイート
- 6.11: NZ為替（TWI / NZD/USD）

Excel構造（各シート共通パターン）:
- Row 0: タイトル
- Row 1: 説明
- Row 2: ソース
- Row 3: ノート（任意）
- Row 4: 列ヘッダー（"Feb MPS", "Nov MPS" 等）
- Row 5: 単位（%, Index, etc.）
- Row 6+: データ（Col 2=日付, Col 3+=値）

発表スケジュール: 2/5/8/11月（MPS発行時）
ファイル更新を自動検知: ファイルのmtime変更でキャッシュを更新
"""
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "newzealand" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "nz_mps_forecast_cache.json"

# MPS Data Pack Excelファイルパス（手動配置）
EXCEL_DIR = Path(__file__).parent.parent.parent / "data" / "excel"

# ファイル名パターン: mps---data.xlsx（置き換え時に自動検知）
MPS_EXCEL_GLOB = "mps*data.xlsx"


# --- シート定義 ---
# 各シートの構造を定義
# simple: 2系列（latest, previous）- Col 2=date, Col 3=latest, Col 4=previous
# multi_latest_previous: 複数系列で latest/previous がペア
# multi_series: 複数系列（latest/previousペアなし）
# projections: Projectionsシート用 - Col 0=date(Row 7+), 列番号で指定

INDICATOR_CONFIGS: Dict[str, Dict[str, Any]] = {
    "ocr": {
        "sheet": "i.1",
        "name_jp": "政策金利（OCR）パス",
        "name_en": "OCR Path",
        "unit": "%",
        "type": "simple",  # Col 3=latest, Col 4=previous
    },
    "gdp_qoq": {
        "sheet": "Projections",
        "name_jp": "GDP前期比",
        "name_en": "GDP Quarterly % Change",
        "unit": "%",
        "type": "projections_compare",  # latest vs previous from 2 MPS files
        "col": 2,  # gdpqpc (Quarterly % change)
    },
    "cpi_headline": {
        "sheet": "2.15",
        "name_jp": "ヘッドラインCPI / Non-tradables / Tradables",
        "name_en": "Headline CPI / Non-tradables / Tradables",
        "unit": "%",
        "type": "multi_series",
        # Col 3=Headline, Col 4=Non-tradables, Col 5=Tradables
        "series": [
            {"col": 3, "key": "headline", "name": "Headline"},
            {"col": 4, "key": "non_tradables", "name": "Non-tradables"},
            {"col": 5, "key": "tradables", "name": "Tradables"},
        ],
    },
    "inflation_components": {
        "sheet": "5.1",
        "name_jp": "インフレ内訳（今回 vs 前回）",
        "name_en": "Inflation Components (Latest vs Previous)",
        "unit": "%",
        "type": "multi_latest_previous",
        # Col 3/4=Headline, Col 5/6=Non-tradables, Col 7/8=Tradables
        "series": [
            {"latest_col": 3, "previous_col": 4, "key": "headline", "name": "Headline"},
            {"latest_col": 5, "previous_col": 6, "key": "non_tradables", "name": "Non-tradables"},
            {"latest_col": 7, "previous_col": 8, "key": "tradables", "name": "Tradables"},
        ],
    },
    "wage_inflation": {
        "sheet": "5.2",
        "name_jp": "民間LCI賃金インフレ",
        "name_en": "Private Sector LCI Wage Inflation",
        "unit": "%",
        "type": "simple",
    },
    "output_gap": {
        "sheet": "2.10",
        "name_jp": "Output Gap",
        "name_en": "Output Gap",
        "unit": "%",
        "type": "simple",
    },
    "unemployment_rate": {
        "sheet": "2.11",
        "name_jp": "失業率",
        "name_en": "Unemployment Rate",
        "unit": "%",
        "type": "simple",
    },
    "neutral_ocr": {
        "sheet": "6.4",
        "name_jp": "OCR & 中立OCRスイート",
        "name_en": "OCR & Neutral OCR Suite",
        "unit": "%",
        "type": "multi_series",
        # Col 3=Long-term mean, Col 4=Forecast horizon mean, Col 5=Short-term mean,
        # Col 6=OCR, Col 7=Lower bound, Col 8=Upper bound
        "series": [
            {"col": 6, "key": "ocr", "name": "OCR"},
            {"col": 3, "key": "long_term_mean", "name": "Long-term (mean)"},
            {"col": 4, "key": "forecast_horizon_mean", "name": "Forecast horizon (mean)"},
            {"col": 5, "key": "short_term_mean", "name": "Short-term (mean)"},
        ],
    },
}


class RbnzMpsForecastService:
    """RBNZ MPS 経済見通しサービス"""

    DATA_CACHE_KEY = "newzealand:nz_economic_forecast:data"

    def __init__(self):
        self._file_mtime: Optional[float] = None

    def _find_mps_excel(self) -> Optional[Path]:
        """MPS Excelファイルを検索（最新のファイルを返す）"""
        import glob
        pattern = str(EXCEL_DIR / MPS_EXCEL_GLOB)
        files = glob.glob(pattern)
        if not files:
            logger.warning(f"No MPS Excel found matching {pattern}")
            return None
        # 最新のファイルを返す
        files.sort(key=os.path.getmtime, reverse=True)
        return Path(files[0])

    def _find_mps_excel_files(self) -> tuple[Optional[Path], Optional[Path]]:
        """MPS Excelファイルを検索し、最新と前回の2ファイルを返す

        Returns:
            (latest_path, previous_path) - 前回が存在しない場合はNone
        """
        import glob
        pattern = str(EXCEL_DIR / MPS_EXCEL_GLOB)
        files = glob.glob(pattern)
        if not files:
            logger.warning(f"No MPS Excel found matching {pattern}")
            return None, None
        files.sort(key=os.path.getmtime, reverse=True)
        latest = Path(files[0])
        previous = Path(files[1]) if len(files) > 1 else None
        return latest, previous

    def _get_file_mtime(self, filepath: Path) -> float:
        """ファイルの最終更新日時を取得"""
        return os.path.getmtime(filepath)

    def get_nz_economic_forecast_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """MPS経済見通しデータを取得"""

        excel_path = self._find_mps_excel()
        if excel_path is None:
            return {
                "indicators": {},
                "metadata": {"source": "RBNZ", "error": "MPS Excel not found"},
                "cached": False,
                "source": "none",
            }

        current_mtime = self._get_file_mtime(excel_path)

        # キャッシュチェック
        if not force_refresh:
            cached_data = redis_client.get(self.DATA_CACHE_KEY)
            if cached_data:
                cached_mtime = cached_data.get("file_mtime")
                if cached_mtime and cached_mtime == current_mtime:
                    return {
                        "indicators": cached_data.get("indicators", {}),
                        "metadata": cached_data.get("metadata", {}),
                        "cached": True,
                        "source": "redis",
                    }

        # Excelからパース
        indicators = self._parse_all_indicators(excel_path)
        if not indicators:
            # ファイルキャッシュフォールバック
            file_cache = self._load_file_cache()
            if file_cache:
                return {
                    "indicators": file_cache.get("indicators", {}),
                    "metadata": file_cache.get("metadata", {}),
                    "cached": True,
                    "source": "file (fallback)",
                }
            return {
                "indicators": {},
                "metadata": {"source": "RBNZ", "error": "Parse failed"},
                "cached": False,
                "source": "none",
            }

        # メタデータ構築
        metadata = self._build_metadata(excel_path)

        cache_payload = {
            "indicators": indicators,
            "metadata": metadata,
            "file_mtime": current_mtime,
            "last_updated": datetime.now(JST).isoformat(),
        }
        redis_client.set(self.DATA_CACHE_KEY, cache_payload, expire=0)
        self._save_file_cache(cache_payload)

        return {
            "indicators": indicators,
            "metadata": metadata,
            "cached": False,
            "source": "excel",
        }

    def _build_metadata(self, excel_path: Path) -> Dict[str, Any]:
        """メタデータを構築"""
        # ファイル名からMPS月を抽出 (例: mpsfeb26-data.xlsx → Feb 2026)
        filename = excel_path.stem.lower()
        mps_label = ""

        month_map = {
            "jan": "January", "feb": "February", "mar": "March",
            "apr": "April", "may": "May", "jun": "June",
            "jul": "July", "aug": "August", "sep": "September",
            "oct": "October", "nov": "November", "dec": "December",
        }

        for abbr, full in month_map.items():
            if abbr in filename:
                # 年を抽出（2桁）
                idx = filename.index(abbr) + len(abbr)
                year_str = filename[idx:idx+2]
                try:
                    year = 2000 + int(year_str)
                    mps_label = f"{full} {year}"
                except ValueError:
                    pass
                break

        # 前回MPSの推定（i.1シートのRow 4 Col 4から）
        previous_label = ""
        try:
            df = pd.read_excel(str(excel_path), sheet_name="i.1", header=None, engine="openpyxl")
            if df.shape[0] > 4 and df.shape[1] > 4:
                prev_val = df.iloc[4, 4]
                if pd.notna(prev_val):
                    previous_label = str(prev_val).strip()
        except Exception:
            pass

        return {
            "source": "Reserve Bank of New Zealand",
            "indicator": "Monetary Policy Statement Economic Projections",
            "latest_publication": mps_label,
            "previous_publication": previous_label,
            "filename": excel_path.name,
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _parse_all_indicators(self, excel_path: Path) -> Dict[str, Any]:
        """全指標をパース"""
        indicators = {}
        excel_str = str(excel_path)

        # projections_compare用に前回ファイルを取得
        _, previous_path = self._find_mps_excel_files()

        for key, config in INDICATOR_CONFIGS.items():
            try:
                sheet_name = config["sheet"]
                df = pd.read_excel(excel_str, sheet_name=sheet_name, header=None, engine="openpyxl")

                if config["type"] == "simple":
                    indicators[key] = self._parse_simple_sheet(df, config)
                elif config["type"] == "multi_series":
                    indicators[key] = self._parse_multi_series_sheet(df, config)
                elif config["type"] == "multi_latest_previous":
                    indicators[key] = self._parse_multi_latest_previous_sheet(df, config)
                elif config["type"] == "projections":
                    indicators[key] = self._parse_projections_sheet(df, config)
                elif config["type"] == "projections_compare":
                    indicators[key] = self._parse_projections_compare(
                        df, config, previous_path
                    )

            except Exception as e:
                logger.warning(f"[MPS] Error parsing {key} ({config['sheet']}): {e}")
                indicators[key] = {
                    "latest": [],
                    "previous": [],
                    "name_jp": config["name_jp"],
                    "name_en": config["name_en"],
                    "unit": config["unit"],
                }

        return indicators

    def _parse_date(self, date_val) -> Optional[str]:
        """日付をYYYY-MM-DD形式に変換"""
        if pd.isna(date_val):
            return None
        if isinstance(date_val, datetime):
            return date_val.strftime("%Y-%m-%d")
        if isinstance(date_val, str):
            try:
                dt = pd.to_datetime(date_val)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                return None
        return None

    def _parse_simple_sheet(self, df: pd.DataFrame, config: Dict) -> Dict[str, Any]:
        """simple型（2系列: latest + previous）をパース

        Col 2 = date, Col 3 = latest, Col 4 = previous
        """
        DATA_START = 6
        latest = []
        previous = []

        for row_idx in range(DATA_START, df.shape[0]):
            date_str = self._parse_date(df.iloc[row_idx, 2])
            if not date_str:
                continue

            lat_val = df.iloc[row_idx, 3] if df.shape[1] > 3 else None
            prev_val = df.iloc[row_idx, 4] if df.shape[1] > 4 else None

            if pd.notna(lat_val):
                try:
                    latest.append({"date": date_str, "value": round(float(lat_val), 2)})
                except (ValueError, TypeError):
                    pass

            if pd.notna(prev_val):
                try:
                    previous.append({"date": date_str, "value": round(float(prev_val), 2)})
                except (ValueError, TypeError):
                    pass

        return {
            "latest": latest,
            "previous": previous,
            "name_jp": config["name_jp"],
            "name_en": config["name_en"],
            "unit": config["unit"],
        }

    def _parse_multi_series_sheet(self, df: pd.DataFrame, config: Dict) -> Dict[str, Any]:
        """multi_series型（複数系列、latest/previousペアなし）をパース"""
        DATA_START = 6
        series_data: Dict[str, List] = {}
        for s in config["series"]:
            series_data[s["key"]] = []

        for row_idx in range(DATA_START, df.shape[0]):
            date_str = self._parse_date(df.iloc[row_idx, 2])
            if not date_str:
                continue

            for s in config["series"]:
                col = s["col"]
                if df.shape[1] > col:
                    val = df.iloc[row_idx, col]
                    if pd.notna(val):
                        try:
                            series_data[s["key"]].append({
                                "date": date_str,
                                "value": round(float(val), 2),
                            })
                        except (ValueError, TypeError):
                            pass

        return {
            "series": series_data,
            "series_config": [
                {"key": s["key"], "name": s["name"]} for s in config["series"]
            ],
            "name_jp": config["name_jp"],
            "name_en": config["name_en"],
            "unit": config["unit"],
        }

    def _parse_multi_latest_previous_sheet(self, df: pd.DataFrame, config: Dict) -> Dict[str, Any]:
        """multi_latest_previous型（複数系列 × latest/previous）をパース

        5.1のように Col 3/4 = headline latest/previous, Col 5/6 = non-tradables latest/previous, ...
        """
        DATA_START = 6
        series_data: Dict[str, Dict[str, List]] = {}
        for s in config["series"]:
            series_data[s["key"]] = {"latest": [], "previous": []}

        for row_idx in range(DATA_START, df.shape[0]):
            date_str = self._parse_date(df.iloc[row_idx, 2])
            if not date_str:
                continue

            for s in config["series"]:
                lat_col = s["latest_col"]
                prev_col = s["previous_col"]

                if df.shape[1] > lat_col:
                    val = df.iloc[row_idx, lat_col]
                    if pd.notna(val):
                        try:
                            series_data[s["key"]]["latest"].append({
                                "date": date_str,
                                "value": round(float(val), 2),
                            })
                        except (ValueError, TypeError):
                            pass

                if df.shape[1] > prev_col:
                    val = df.iloc[row_idx, prev_col]
                    if pd.notna(val):
                        try:
                            series_data[s["key"]]["previous"].append({
                                "date": date_str,
                                "value": round(float(val), 2),
                            })
                        except (ValueError, TypeError):
                            pass

        return {
            "series": series_data,
            "series_config": [
                {"key": s["key"], "name": s["name"]} for s in config["series"]
            ],
            "name_jp": config["name_jp"],
            "name_en": config["name_en"],
            "unit": config["unit"],
        }

    def _parse_projections_sheet(self, df: pd.DataFrame, config: Dict) -> Dict[str, Any]:
        """Projections シートから単一列のデータを取得

        Projections シート構造:
        - Row 0-1: 注記
        - Row 2: 系列名
        - Row 5: 単位
        - Row 6: 識別子
        - Row 7+: データ（Col 0=datetime, config["col"]=値）
        """
        DATA_START = 7
        col = config["col"]
        data = []

        for row_idx in range(DATA_START, df.shape[0]):
            date_str = self._parse_date(df.iloc[row_idx, 0])
            if not date_str:
                continue

            if df.shape[1] > col:
                val = df.iloc[row_idx, col]
                if pd.notna(val):
                    try:
                        data.append({
                            "date": date_str,
                            "value": round(float(val), 2),
                        })
                    except (ValueError, TypeError):
                        pass

        return {
            "data": data,
            "name_jp": config["name_jp"],
            "name_en": config["name_en"],
            "unit": config["unit"],
        }

    def _parse_projections_compare(
        self, latest_df: pd.DataFrame, config: Dict, previous_path: Optional[Path]
    ) -> Dict[str, Any]:
        """projections_compare型: 最新と前回のMPSファイルから同じ列を比較

        latest_df: 最新MPS ExcelのProjectionsシート（既読み込み済み）
        previous_path: 前回MPS Excelのパス
        """
        DATA_START = 7
        col = config["col"]

        # 最新データ
        latest = []
        for row_idx in range(DATA_START, latest_df.shape[0]):
            date_str = self._parse_date(latest_df.iloc[row_idx, 0])
            if not date_str:
                continue
            if latest_df.shape[1] > col:
                val = latest_df.iloc[row_idx, col]
                if pd.notna(val):
                    try:
                        latest.append({"date": date_str, "value": round(float(val), 2)})
                    except (ValueError, TypeError):
                        pass

        # 前回データ
        previous = []
        if previous_path:
            try:
                prev_df = pd.read_excel(
                    str(previous_path), sheet_name=config["sheet"],
                    header=None, engine="openpyxl"
                )
                for row_idx in range(DATA_START, prev_df.shape[0]):
                    date_str = self._parse_date(prev_df.iloc[row_idx, 0])
                    if not date_str:
                        continue
                    if prev_df.shape[1] > col:
                        val = prev_df.iloc[row_idx, col]
                        if pd.notna(val):
                            try:
                                previous.append({"date": date_str, "value": round(float(val), 2)})
                            except (ValueError, TypeError):
                                pass
                logger.info(f"[MPS] projections_compare: latest={len(latest)} pts, previous={len(previous)} pts from {previous_path.name}")
            except Exception as e:
                logger.warning(f"[MPS] Error reading previous MPS file {previous_path}: {e}")

        return {
            "latest": latest,
            "previous": previous,
            "name_jp": config["name_jp"],
            "name_en": config["name_en"],
            "unit": config["unit"],
        }

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[MPS] Failed to load file cache: {e}")
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[MPS] Failed to save file cache: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        excel_path = self._find_mps_excel()
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached_data = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None
        return {
            "indicator": "RBNZ MPS Economic Projections",
            "source": "RBNZ",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
            "excel_path": str(excel_path) if excel_path else None,
            "excel_mtime": self._get_file_mtime(excel_path) if excel_path else None,
        }


# シングルトンインスタンス
rbnz_mps_forecast_service = RbnzMpsForecastService()
