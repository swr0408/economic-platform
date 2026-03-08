"""
中国 資本フロー（Capital Flows）サービス

データソース:
  SAFE (State Administration of Foreign Exchange)
  银行代客涉外收付款数据时间序列
  Sheet: 以美元计值（月度）
  単位: 亿美元 (100 million USD)

対象系列（三、收支差额 = Net Balance セクション）:
  Row 40: net_total     三、收支差额          収支差額合計
  Row 42: net_current   1.经常账户            経常勘定ネット
  Row 43: net_goods     1.1货物贸易           貨物貿易ネット
  Row 44: net_services  1.2服务               サービスネット
  Row 46: net_capital   2.资本和金融账户       資本・金融勘定ネット
  Row 48: net_securities 证券投资              証券投資ネット
  Row 49: net_other     其他投资              その他投資ネット

取得方法:
  1. SAFEページからExcelリンクを動的取得（URLが毎月変わるため）
  2. フォールバック: 固定URL
  3. Sheet「以美元计值（月度）」を読み込み、Row 3 からヘッダー、対象行から値を抽出

発表スケジュール: 月次（PDFからパース）
キャッシュ: Redis + ファイルキャッシュ
"""
import io
import json
import logging
import re
from datetime import date, datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from zoneinfo import ZoneInfo
import glob as glob_module

import pandas as pd
import requests
from bs4 import BeautifulSoup

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
REDIS_KEY = "china:cn_capital_flows:data"
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "china" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
FILE_CACHE = CACHE_DIR / "cn_capital_flows_cache.json"

# PDF ディレクトリ
PDF_DIR = Path(__file__).parent.parent.parent / "data" / "pdf" / "china"

# SAFE ページURL（Excelリンクが掲載されている）
SAFE_PAGE_URL = "https://www.safe.gov.cn/safe/2018/0419/8806.html"

# フォールバック Excel URL（2026-02-13 更新分）
FALLBACK_EXCEL_URL = (
    "https://www.safe.gov.cn/safe/file/file/20260213/"
    "53eb84692eb54d50b84838f84bf6fe7d.xls"
    "?n=%E9%93%B6%E8%A1%8C%E4%BB%A3%E5%AE%A2%E6%B6%89%E5%A4%96"
    "%E6%94%B6%E4%BB%98%E6%AC%BE%E6%95%B0%E6%8D%AE%E6%97%B6%E9%97%B4%E5%BA%8F%E5%88%97"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Excel構造定数
SHEET_NAME = "以美元计值（月度）"
HEADER_ROW = 3

# 対象行: key → row index (0-based)
TARGET_ROWS: Dict[str, int] = {
    "net_total": 40,
    "net_current": 42,
    "net_goods": 43,
    "net_services": 44,
    "net_capital": 46,
    "net_securities": 48,
    "net_other": 49,
}

# 2026年の発表スケジュール（フォールバック）
FALLBACK_SCHEDULE_2026 = [
    "2026-01-15", "2026-02-13", "2026-03-16", "2026-04-15",
    "2026-05-18", "2026-06-15", "2026-07-17", "2026-08-17",
    "2026-09-15", "2026-10-20", "2026-11-16", "2026-12-15",
]


# =============================================================================
# Excel URL 動的取得
# =============================================================================

def _discover_excel_url() -> Optional[str]:
    """SAFEページをスクレイプして最新のExcelダウンロードURLを取得"""
    try:
        resp = requests.get(SAFE_PAGE_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        for a_tag in soup.find_all("a", href=True):
            text = a_tag.get_text(strip=True)
            if "银行代客涉外收付款数据时间序列" in text:
                href = a_tag["href"]
                if href.startswith("/"):
                    href = "https://www.safe.gov.cn" + href
                logger.info(f"[CapitalFlows] Discovered Excel URL: {href[:80]}...")
                return href

        logger.warning("[CapitalFlows] Could not find Excel link on SAFE page")
        return None
    except Exception as e:
        logger.warning(f"[CapitalFlows] Failed to scrape SAFE page: {e}")
        return None


def _download_excel() -> Optional[bytes]:
    """SAFE Excelファイルをダウンロード"""
    # まず動的URL取得を試行
    url = _discover_excel_url()
    if not url:
        url = FALLBACK_EXCEL_URL
        logger.info("[CapitalFlows] Using fallback Excel URL")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        if resp.status_code != 200:
            # フォールバック再試行
            if url != FALLBACK_EXCEL_URL:
                logger.warning(f"[CapitalFlows] Dynamic URL failed ({resp.status_code}), trying fallback")
                resp = requests.get(FALLBACK_EXCEL_URL, headers=HEADERS, timeout=60)
                if resp.status_code != 200:
                    logger.error(f"[CapitalFlows] Fallback also failed: HTTP {resp.status_code}")
                    return None
            else:
                logger.error(f"[CapitalFlows] Download failed: HTTP {resp.status_code}")
                return None

        logger.info(f"[CapitalFlows] Excel downloaded: {len(resp.content)} bytes")
        return resp.content
    except Exception as e:
        logger.error(f"[CapitalFlows] Download error: {e}")
        return None


# =============================================================================
# Excel パース
# =============================================================================

def _parse_excel(excel_bytes: bytes) -> List[Dict[str, Any]]:
    """ExcelからCapital Flowsデータを抽出"""
    try:
        df = pd.read_excel(
            io.BytesIO(excel_bytes),
            sheet_name=SHEET_NAME,
            header=None,
        )
    except Exception as e:
        logger.error(f"[CapitalFlows] Excel read error: {e}")
        return []

    # ヘッダー行から月次カラムを取得
    header_row = df.iloc[HEADER_ROW]
    col_dates: Dict[int, str] = {}

    for col_idx in range(1, len(header_row)):
        raw = header_row.iloc[col_idx]
        if pd.isna(raw):
            continue
        try:
            if isinstance(raw, datetime):
                date_str = raw.strftime("%Y-%m-01")
            elif isinstance(raw, str):
                dt = pd.to_datetime(raw)
                date_str = dt.strftime("%Y-%m-01")
            else:
                continue
            col_dates[col_idx] = date_str
        except Exception:
            continue

    if not col_dates:
        logger.error("[CapitalFlows] No date columns found in header row")
        return []

    # 各系列の値を抽出
    series_data: Dict[str, Dict[str, Optional[float]]] = {
        key: {} for key in TARGET_ROWS
    }

    for key, row_idx in TARGET_ROWS.items():
        if row_idx >= len(df):
            logger.warning(f"[CapitalFlows] Row {row_idx} ({key}) out of range")
            continue

        data_row = df.iloc[row_idx]
        for col_idx, date_str in col_dates.items():
            if col_idx >= len(data_row):
                continue
            val = data_row.iloc[col_idx]
            if pd.isna(val):
                series_data[key][date_str] = None
            else:
                try:
                    series_data[key][date_str] = round(float(val), 1)
                except (ValueError, TypeError):
                    series_data[key][date_str] = None

    # 日付でマージ
    all_dates = sorted(col_dates.values())
    result: List[Dict[str, Any]] = []

    for d in all_dates:
        record: Dict[str, Any] = {"date": d}
        has_any = False
        for key in TARGET_ROWS:
            val = series_data[key].get(d)
            record[key] = val
            if val is not None:
                has_any = True
        if has_any:
            result.append(record)

    logger.info(f"[CapitalFlows] Parsed {len(result)} monthly records")
    if result:
        logger.info(f"[CapitalFlows] Range: {result[0]['date']} ~ {result[-1]['date']}")
        latest = result[-1]
        logger.info(
            f"[CapitalFlows] Latest: {latest['date']} "
            f"net_total={latest.get('net_total')}, "
            f"net_capital={latest.get('net_capital')}"
        )

    return result


# =============================================================================
# PDF スケジュールパース
# =============================================================================

def _parse_schedule_from_pdf() -> List[str]:
    """PDFからリリーススケジュールを抽出"""
    try:
        import pdfplumber
    except ImportError:
        logger.warning("[CapitalFlows] pdfplumber not available, using fallback schedule")
        return FALLBACK_SCHEDULE_2026

    # 最新年のPDFを検索
    pattern = str(PDF_DIR / "中国資本フロースケジュール*.pdf")
    pdf_files = sorted(glob_module.glob(pattern))
    if not pdf_files:
        logger.warning("[CapitalFlows] No schedule PDF found, using fallback")
        return FALLBACK_SCHEDULE_2026

    pdf_path = pdf_files[-1]  # 最新年のファイル
    # ファイル名から年を抽出
    year_match = re.search(r"(\d{4})", Path(pdf_path).name)
    year = int(year_match.group(1)) if year_match else date.today().year

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row:
                            continue
                        # 「银行代客涉外收付款数据」を含む行を探す
                        row_text = " ".join(str(cell or "") for cell in row)
                        if "银行代客涉外收付款数据" not in row_text:
                            continue
                        if "时间序列" in row_text:
                            continue  # 時間序列リンクは別行

                        # この行から月次日付を抽出
                        # フォーマット: "15/四", "13/五", "16/一" etc.
                        dates = []
                        day_pattern = re.compile(r"(\d{1,2})/[一二三四五六日]")
                        for i, cell in enumerate(row):
                            if not cell:
                                continue
                            m = day_pattern.search(str(cell))
                            if m:
                                day = int(m.group(1))
                                # セルのインデックスから月を推定
                                # テーブルヘッダー: 報表内容, 1月, 2月, ..., 12月, 発布頻率
                                # → セル1=1月, セル2=2月, ...
                                month = i  # 1-indexed if first cell is label
                                if 1 <= month <= 12:
                                    dates.append(f"{year}-{month:02d}-{day:02d}")

                        if dates:
                            logger.info(f"[CapitalFlows] Extracted {len(dates)} schedule dates from PDF")
                            return dates

        logger.warning("[CapitalFlows] Could not extract schedule from PDF")
    except Exception as e:
        logger.warning(f"[CapitalFlows] PDF parse error: {e}")

    return FALLBACK_SCHEDULE_2026


def _get_next_release_date() -> Optional[Dict[str, Any]]:
    """次回発表日を返す"""
    schedule = _parse_schedule_from_pdf()
    today_str = date.today().isoformat()

    for date_str in schedule:
        if date_str > today_str:
            return {
                "date": date_str,
                "label": "银行代客涉外收付款数据",
            }
    return None


# =============================================================================
# キャッシュ管理
# =============================================================================

def _load_file_cache() -> Optional[Dict[str, Any]]:
    try:
        if FILE_CACHE.exists():
            with open(FILE_CACHE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _save_file_cache(payload: Dict[str, Any]) -> None:
    try:
        with open(FILE_CACHE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _should_refresh(last_updated_str: Optional[str]) -> bool:
    """発表スケジュールベースの更新判定"""
    if not last_updated_str:
        return True

    try:
        last_updated = datetime.fromisoformat(last_updated_str)
    except (ValueError, TypeError):
        return True

    schedule = _parse_schedule_from_pdf()
    now = datetime.now(JST)

    for date_str in schedule:
        try:
            release_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(
                hour=16, minute=0, tzinfo=JST  # 発表は午後想定
            )
        except ValueError:
            continue

        # 発表日を過ぎていて、かつ最終更新がそれより前なら更新
        if now >= release_dt and last_updated < release_dt:
            logger.info(f"[CapitalFlows] Refresh needed: release={date_str}, last_updated={last_updated_str}")
            return True

    return False


# =============================================================================
# メインサービスクラス
# =============================================================================

class CnCapitalFlowsService:
    """中国資本フロー（銀行代客涉外収付款）サービス"""

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """資本フローデータを取得"""
        next_release = _get_next_release_date()

        if not force_refresh:
            try:
                cached = redis_client.get(REDIS_KEY)
                if cached:
                    data = cached if isinstance(cached, dict) else json.loads(cached)
                    last_updated = data.get("last_updated")
                    if last_updated and not _should_refresh(last_updated):
                        data["next_release"] = next_release
                        return data
            except Exception:
                pass

            fc = _load_file_cache()
            if fc and not force_refresh:
                last_updated = fc.get("last_updated")
                if last_updated and not _should_refresh(last_updated):
                    fc["next_release"] = next_release
                    return fc

        # SAFE Excelからデータ取得
        excel_bytes = _download_excel()
        if excel_bytes:
            records = _parse_excel(excel_bytes)
            if records:
                latest = records[-1]
                payload = {
                    "data": records,
                    "latest": latest,
                    "metadata": {
                        "source": "SAFE (State Administration of Foreign Exchange)",
                        "indicator": "银行代客涉外收付款数据",
                        "unit": "100 million USD",
                        "frequency": "monthly",
                        "series": list(TARGET_ROWS.keys()),
                    },
                    "next_release": next_release,
                    "last_updated": datetime.now(JST).isoformat(),
                }
                self._save_to_cache(payload)
                return payload

        # ファイルキャッシュフォールバック
        fc = _load_file_cache()
        if fc:
            fc["next_release"] = next_release
            return fc

        return {
            "data": [],
            "latest": None,
            "metadata": {"source": "SAFE", "error": "No data available"},
            "next_release": next_release,
        }

    def _save_to_cache(self, payload: Dict[str, Any]) -> None:
        try:
            redis_client.set(REDIS_KEY, payload, expire=0)
        except Exception:
            pass
        _save_file_cache(payload)

    def invalidate_cache(self) -> Dict[str, Any]:
        try:
            redis_client.delete(REDIS_KEY)
        except Exception:
            pass
        if FILE_CACHE.exists():
            FILE_CACHE.unlink()
        return {"success": True, "message": "Capital Flows cache invalidated"}

    def get_cache_status(self) -> Dict[str, Any]:
        redis_exists = False
        try:
            redis_exists = redis_client.exists(REDIS_KEY) > 0
        except Exception:
            pass
        fc = _load_file_cache()
        return {
            "indicator": "CN Capital Flows",
            "source": "SAFE",
            "cache_key": REDIS_KEY,
            "redis_cached": redis_exists,
            "file_cached": FILE_CACHE.exists(),
            "file_cache_records": len(fc.get("data", [])) if fc else 0,
            "last_updated": fc.get("last_updated") if fc else None,
            "next_release": _get_next_release_date(),
        }


# シングルトン
cn_capital_flows_service = CnCapitalFlowsService()
