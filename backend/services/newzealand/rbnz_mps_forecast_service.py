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

データ取得:
- 一次: RBNZ公式サイトから最新MPS Data Packを自動ダウンロード（sitemap→詳細ページ→CDN直リンク）
- 取得済みファイルは data/excel/mps*data.xlsx に保存し、mtime変更でキャッシュ更新
- 手動配置も従来どおり可（自動取得が失敗してもファイルがあれば動作）
"""
import io
import json
import logging
import os
import re
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

# --- RBNZ自動ダウンロード設定 ---
# RBNZはCloudflare配下で requests/httpx の TLSフィンガープリントをブロックするため、
# curl/wget の CLI で取得する（_cli_fetch）。下記ヘッダはcurl/wgetの -H/--header に渡す。
# 起点は安定取得できる sitemap.xml → MPS詳細ページ → /-/media/ CDN直リンク（xlsx）。
RBNZ_BASE = "https://www.rbnz.govt.nz"
RBNZ_SITEMAP_URL = f"{RBNZ_BASE}/sitemap.xml"
RBNZ_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}
# 自動チェックのレート制限（秒）。ダッシュボード再構築毎のネットワーク発火を防ぐ。
AUTO_CHECK_INTERVAL_SEC = 12 * 3600
AUTO_CHECK_KEY = "newzealand:nz_mps:auto_check_ts"

MONTH_NAME_TO_IDX = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
MONTH_IDX_TO_ABBR = {
    1: "jan", 2: "feb", 3: "mar", 4: "apr", 5: "may", 6: "jun",
    7: "jul", 8: "aug", 9: "sep", 10: "oct", 11: "nov", 12: "dec",
}
# Data Pack検証用の必須シート（本物のMPSデータパックか確認）
REQUIRED_SHEETS = ["i.1", "Projections", "2.15", "6.4"]


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

    # ========================================================================
    # RBNZ自動ダウンロード（取りこぼし防止）
    # ========================================================================

    def _cli_fetch(self, url: str, retries: int = 1) -> Optional[bytes]:
        """curl または wget（利用可能な方）でURLを取得し bytes を返す。

        RBNZはCloudflare配下で requests/httpx の TLSフィンガープリントをブロックするため
        CLIツールで取得する（姉妹の `rbnz_policy_rate_service._download_via_cli` と同方式）。
        環境によりcurl/wgetのどちらが入るか異なる（本番Dockerfile.simpleはwgetのみ、
        別構成はcurlのみ）ため両対応。Cloudflareは断続的に403を返すので軽くリトライ＋バックオフ。
        全体は12時間に1回のレート制限下で呼ばれるため、失敗しても次回チェックで回復すれば十分。
        """
        import shutil
        import subprocess
        import tempfile
        import time

        ua = RBNZ_BROWSER_HEADERS["User-Agent"]
        accept = RBNZ_BROWSER_HEADERS["Accept"]
        accept_lang = RBNZ_BROWSER_HEADERS["Accept-Language"]

        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            downloaders = []
            if shutil.which("curl"):
                downloaders.append((
                    "curl",
                    ["curl", "-fL", "-o", tmp_path,
                     "-H", f"User-Agent: {ua}", "-H", f"Accept: {accept}",
                     "-H", f"Accept-Language: {accept_lang}",
                     "--max-time", "90", "-s", url],
                ))
            if shutil.which("wget"):
                downloaders.append((
                    "wget",
                    ["wget", "-q", "-O", tmp_path,
                     f"--header=User-Agent: {ua}", f"--header=Accept: {accept}",
                     f"--header=Accept-Language: {accept_lang}",
                     "--timeout=90", url],
                ))
            if not downloaders:
                logger.warning("[MPS auto] neither curl nor wget is available")
                return None

            for attempt in range(retries + 1):
                if attempt > 0:
                    time.sleep(3)  # バックオフ（Cloudflareブロック誘発を避ける）
                for name, cmd in downloaders:
                    try:
                        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    except Exception as e:
                        logger.warning(f"[MPS auto] {name} error for {url}: {e}")
                        continue
                    if proc.returncode == 0 and os.path.getsize(tmp_path) > 0:
                        with open(tmp_path, "rb") as f:
                            return f.read()
                    logger.warning(
                        f"[MPS auto] {name} failed for {url} "
                        f"(exit {proc.returncode}, attempt {attempt + 1}/{retries + 1})"
                    )
            return None
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    def _parse_mps_from_filename(self, name: str) -> Optional[tuple[int, int]]:
        """ファイル名からMPSの(年, 月index)を抽出（例: mpsmay26-data.xlsx → (2026, 5)）"""
        n = name.lower()
        for idx, abbr in MONTH_IDX_TO_ABBR.items():
            m = re.search(rf"mps{abbr}(\d{{2}})", n)
            if m:
                return (2000 + int(m.group(1)), idx)
        return None

    def _discover_latest_datapack(self) -> Optional[tuple[str, int, int]]:
        """sitemap → 最新MPS詳細ページ → Data Pack xlsx URL を解決。

        Returns:
            (datapack_url, year, month_idx) または None
        """
        sitemap_bytes = self._cli_fetch(RBNZ_SITEMAP_URL, retries=1)
        if not sitemap_bytes:
            logger.warning("[MPS auto] sitemap fetch failed")
            return None
        sitemap_text = sitemap_bytes.decode("utf-8", errors="replace")

        # MPSレポート詳細ページ（filtered-listing-page配下のみ。eventsやweb-versionは除外）
        detail_urls = re.findall(
            r"<loc>(https://www\.rbnz\.govt\.nz/monetary-policy/monetary-policy-statement/"
            r"monetary-policy-statement-filtered-listing-page/\d{4}/[a-z]+-\d+/"
            r"monetary-policy-statement-[a-z]+-\d{4})</loc>",
            sitemap_text, re.I,
        )
        candidates = []
        for u in detail_urls:
            if u.lower().endswith("/web-version"):
                continue
            m = re.search(r"/(\d{4})/[a-z]+-\d+/monetary-policy-statement-([a-z]+)-(\d{4})", u, re.I)
            if not m:
                continue
            month_idx = MONTH_NAME_TO_IDX.get(m.group(2).lower())
            if not month_idx:
                continue
            candidates.append((int(m.group(3)), month_idx, u))

        if not candidates:
            logger.warning("[MPS auto] no MPS detail pages found in sitemap")
            return None

        candidates.sort()
        year, month_idx, detail_url = candidates[-1]

        # 詳細ページから Data Pack xlsx リンクを抽出（パスセグメントは日付から導出不能なため必須）
        page_bytes = self._cli_fetch(detail_url, retries=1)
        if not page_bytes:
            logger.warning(f"[MPS auto] detail page fetch failed: {detail_url}")
            return None
        page_text = page_bytes.decode("utf-8", errors="replace")
        m = re.search(r"(/-/media/[^\"']+mps[a-z]+\d{2}-data\.xlsx)", page_text, re.I)
        if not m:
            logger.warning(f"[MPS auto] data pack link not found on {detail_url}")
            return None
        return (RBNZ_BASE + m.group(1), year, month_idx)

    def _validate_datapack(self, content: bytes) -> bool:
        """ダウンロードしたxlsxが本物のMPSデータパックか検証（必須シート存在確認）"""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
            sheets = set(wb.sheetnames)
            wb.close()
            missing = [s for s in REQUIRED_SHEETS if s not in sheets]
            if missing:
                logger.warning(f"[MPS auto] downloaded xlsx missing required sheets: {missing}")
                return False
            return True
        except Exception as e:
            logger.warning(f"[MPS auto] validation failed: {e}")
            return False

    def _maybe_auto_update(self, force_refresh: bool = False) -> None:
        """RBNZ最新MPS Data Packを自動取得して data/excel に配置（レート制限付き・best-effort）。

        失敗しても既存ファイルでの動作は維持される（取得経路の追加であって置換ではない）。
        """
        try:
            # レート制限: force_refresh以外は直近チェック済みならスキップ
            if not force_refresh and redis_client.get(AUTO_CHECK_KEY):
                return
            # 先にキー設定（失敗時の連打防止・TTLで自然回復）
            redis_client.set(AUTO_CHECK_KEY, datetime.now(JST).isoformat(), expire=AUTO_CHECK_INTERVAL_SEC)

            current = self._find_mps_excel()
            current_ym = self._parse_mps_from_filename(current.name) if current else None

            discovered = self._discover_latest_datapack()
            if not discovered:
                return
            datapack_url, year, month_idx = discovered

            # 既に最新（以上）を保持していれば何もしない
            if current_ym and (year, month_idx) <= current_ym:
                return

            filename = datapack_url.rsplit("/", 1)[-1]
            target = EXCEL_DIR / filename
            if target.exists():
                return  # 既にDL済み（mtime検知は別途get_*で処理）

            content = self._cli_fetch(datapack_url, retries=1)
            if not content:
                logger.warning(f"[MPS auto] data pack download failed: {datapack_url}")
                return
            if not self._validate_datapack(content):
                return

            EXCEL_DIR.mkdir(parents=True, exist_ok=True)
            with open(target, "wb") as f:
                f.write(content)
            logger.info(f"[MPS auto] downloaded new MPS data pack: {filename} ({year}-{month_idx:02d})")
        except Exception as e:
            logger.warning(f"[MPS auto] auto-update error: {e}")

    def get_nz_economic_forecast_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """MPS経済見通しデータを取得"""

        # 新しいMPS Data Packが公表されていれば自動取得（レート制限付き・best-effort）。
        # 取得できた場合はファイルmtimeが変わり、下のキャッシュ判定で自動的に再パースされる。
        self._maybe_auto_update(force_refresh=force_refresh)

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
        """日付をYYYY-MM-DD形式に変換

        注: simple/multi_*シート(i.1,2.10,2.11,5.1,5.2)のCol2は文字列の
        DD/MM/YYYY形式(NZ式、例 '01/03/2008'=2008年3月1日=Q1)。pandas既定は
        米国式MM/DD/YYYYで '01/03/2008' を1月3日と誤解釈するため dayfirst=True 必須。
        (Projectionsシートは datetime 型なのでこの分岐に来ない)
        """
        if pd.isna(date_val):
            return None
        if isinstance(date_val, datetime):
            return date_val.strftime("%Y-%m-%d")
        if isinstance(date_val, str):
            try:
                dt = pd.to_datetime(date_val, dayfirst=True)
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
