"""
中国インターバンク市場 Fixing Repo Rate サービス

データソース:
  - 過去データ: backend/data/excel/Fixing_Repo_Rate_Historical_Data_{yyyy}.xlsx
  - 最新データ: chinamoney.com.cn 内部 API（毎日当年ファイルを更新）

対象系列:
  FR001, FR007, FR014  (Fixing Repo Rate - 銀行間)
  FDR001, FDR007, FDR014 (Fixing Depository-institutions Repo Rate - 預金取扱機関間)

Excelファイル構造:
  Row 0: ヘッダー ['Date', 'FR001(%)', 'FR007(%)', 'FR014(%)', 'FDR001(%)', 'FDR007(%)', 'FDR014(%)']
  Row 1+: データ行 ('02 Mar 2026', '1.3900', ...)
  最終2行: フッター ('Data source:', ...) - スキップ

更新方式:
  - 毎日 14:00 CST 以降: 当年 API 取得 → 当年 Excel 上書き → Redis キャッシュ再構築
  - 初回 / force_refresh: 全年 Excel 読み込み + 当年 API 取得

キャッシュ: Redis TTL 6時間 + ファイルキャッシュ（フォールバック）
"""
import json
import time
import logging
from datetime import date, datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from core.redis_client import redis_client

logger = logging.getLogger("cn_fixing_repo_rate_service")

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
REDIS_KEY = "china:cn_fixing_repo_rate:data"
REDIS_TTL = 6 * 3600  # 6時間

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "china" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
FILE_CACHE = CACHE_DIR / "cn_fixing_repo_rate_cache.json"

# Excel ディレクトリ
EXCEL_DIR = Path(__file__).parent.parent.parent / "data" / "excel"

# API設定
API_URL = "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-currency/FrrHis"
API_HEADERS = {
    "Referer": "https://www.chinamoney.com.cn/english/bmkfrr/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

ALL_SERIES = ["FR001", "FR007", "FR014", "FDR001", "FDR007", "FDR014"]


# =============================================================================
# Excel 読み込み
# =============================================================================

def _excel_path(year: int) -> Path:
    return EXCEL_DIR / f"Fixing_Repo_Rate_Historical_Data_{year}.xlsx"


def _read_excel_year(year: int) -> List[Dict[str, Any]]:
    """
    指定年のExcelを読み込んでレコードリストを返す。
    ファイルが存在しない場合は空リストを返す。
    """
    path = _excel_path(year)
    if not path.exists():
        return []

    try:
        df = pd.read_excel(path, header=None)
    except Exception as e:
        logger.error(f"[FRR] Excel read error ({year}): {e}")
        return []

    records = []
    for i in range(1, len(df)):  # Row 0 はヘッダー
        row = df.iloc[i]
        date_raw = row.iloc[0]
        # フッター行スキップ（"Data source:" or NaN）
        if pd.isna(date_raw) or str(date_raw).strip().startswith("Data source"):
            continue
        try:
            dt = datetime.strptime(str(date_raw).strip(), "%d %b %Y").date()
            date_str = dt.isoformat()
        except ValueError:
            continue

        rec: Dict[str, Any] = {"date": date_str}
        for j, series in enumerate(ALL_SERIES, start=1):
            raw = row.iloc[j]
            try:
                rec[series] = float(raw) if not pd.isna(raw) else None
            except (ValueError, TypeError):
                rec[series] = None
        records.append(rec)

    return records


def _load_all_excel() -> List[Dict[str, Any]]:
    """全年Excelを読み込んで昇順に結合して返す"""
    current_year = date.today().year
    all_records: Dict[str, Dict[str, Any]] = {}

    start_year = 2018  # 最初の年
    for year in range(start_year, current_year + 1):
        rows = _read_excel_year(year)
        for row in rows:
            all_records[row["date"]] = row

    return sorted(all_records.values(), key=lambda x: x["date"])


# =============================================================================
# API 取得
# =============================================================================

def _date_to_api_fmt(d: date) -> str:
    """日付を API フォーマットに変換 (例: "01 Jan 2026")"""
    return d.strftime("%d %b %Y")


def _fetch_year_from_api(year: int) -> List[Dict[str, Any]]:
    """
    指定年のデータを API から取得して返す。
    API は1回のリクエストで最大約240日分のため、
    当年・前年は1回、それ以前は複数回に分けて取得する。
    ここでは当年のみ想定（差分更新用）。
    """
    start = date(year, 1, 1)
    end = min(date(year, 12, 31), date.today())

    ts = int(time.time() * 1000)
    params = {
        "lang": "EN",
        "startDate": _date_to_api_fmt(start),
        "endDate": _date_to_api_fmt(end),
        "t": ts,
        "_": ts - 1000,
    }
    try:
        resp = requests.get(API_URL, params=params, headers=API_HEADERS, timeout=30)
        resp.raise_for_status()
        api_data = resp.json()
    except Exception as e:
        logger.error(f"[FRR] API error (year={year}): {e}")
        return []

    records = []
    for rec in api_data.get("records", []):
        date_str = rec.get("lfiProducDate")
        if not date_str:
            continue
        frm = rec.get("frValueMap", {})
        row: Dict[str, Any] = {"date": date_str}
        for series in ALL_SERIES:
            raw = frm.get(series)
            try:
                row[series] = float(raw) if raw is not None else None
            except (ValueError, TypeError):
                row[series] = None
        records.append(row)

    records.sort(key=lambda x: x["date"])
    return records


def _save_year_to_excel(year: int, records: List[Dict[str, Any]]) -> None:
    """
    レコードリストを当年Excelに上書き保存。
    既存の日付は上書き、新規は追加。既存Excelが存在する場合はマージする。
    """
    path = _excel_path(year)

    # 既存Excelのデータをベースにする
    existing = {r["date"]: r for r in _read_excel_year(year)}
    for row in records:
        existing[row["date"]] = row

    sorted_rows = sorted(existing.values(), key=lambda x: x["date"], reverse=True)

    # DataFrame作成 (降順: 最新が上)
    rows_for_df = []
    for row in sorted_rows:
        rows_for_df.append([
            datetime.strptime(row["date"], "%Y-%m-%d").strftime("%d %b %Y"),
            str(row.get("FR001") or ""),
            str(row.get("FR007") or ""),
            str(row.get("FR014") or ""),
            str(row.get("FDR001") or ""),
            str(row.get("FDR007") or ""),
            str(row.get("FDR014") or ""),
        ])

    header = [["Date", "FR001(%)", "FR007(%)", "FR014(%)", "FDR001(%)", "FDR007(%)", "FDR014(%)"]]
    footer = [
        ["Data source:", "China Foreign Exchange Trade System (CFETS)", "", "", "", "", ""],
        ["", "www.chinamoney.com.cn/english/", "", "", "", "", ""],
    ]

    df = pd.DataFrame(header + rows_for_df + footer)
    try:
        df.to_excel(path, index=False, header=False)
        logger.info(f"[FRR] Saved {len(rows_for_df)} rows to {path.name}")
    except Exception as e:
        logger.error(f"[FRR] Excel write error ({year}): {e}")


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


def _invalidate_cache() -> None:
    try:
        redis_client.delete(REDIS_KEY)
    except Exception:
        pass
    try:
        if FILE_CACHE.exists():
            FILE_CACHE.unlink()
    except Exception:
        pass


# =============================================================================
# ペイロード構築
# =============================================================================

def _build_payload(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    latest = records[-1] if records else None
    return {
        "data": records,
        "latest": latest,
        "metadata": {
            "source": "China Foreign Exchange Trade System (CFETS) / chinamoney.com.cn",
            "unit": "%",
            "frequency": "daily",
            "series": ALL_SERIES,
            "total_records": len(records),
        },
    }


# =============================================================================
# メインサービスクラス
# =============================================================================

class CnFixingRepoRateService:
    """
    中国 Fixing Repo Rate (FR/FDR) サービス

    - 全年 Excel を読み込んで時系列データを提供
    - 毎日: 当年 API 取得 → 当年 Excel 上書き → キャッシュ再構築
    """

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """FR/FDR 全系列の時系列データを返す"""
        if not force_refresh:
            # Redis キャッシュ確認
            try:
                cached = redis_client.get(REDIS_KEY)
                if cached:
                    return json.loads(cached) if isinstance(cached, str) else cached
            except Exception:
                pass
            # ファイルキャッシュ確認
            fc = _load_file_cache()
            if fc:
                return fc

        # 全年 Excel 読み込み
        records = _load_all_excel()
        if not records:
            fc = _load_file_cache()
            if fc:
                return fc
            return {"data": [], "latest": None, "metadata": {}}

        payload = _build_payload(records)
        self._save_to_cache(payload)
        return payload

    def update_current_year(self) -> Dict[str, Any]:
        """
        当年データを API から取得 → 当年 Excel 上書き → キャッシュ再構築

        毎日 14:00 CST 以降に呼び出す差分更新メソッド。
        """
        current_year = date.today().year

        # API から当年データを取得
        api_records = _fetch_year_from_api(current_year)
        if not api_records:
            logger.warning(f"[FRR] API returned no records for {current_year}")
            return self.get_data()

        # 当年 Excel に保存（マージ上書き）
        _save_year_to_excel(current_year, api_records)

        # キャッシュ無効化 → 全 Excel 再読み込み
        _invalidate_cache()
        records = _load_all_excel()
        payload = _build_payload(records)
        self._save_to_cache(payload)

        latest = payload.get("latest", {}) or {}
        logger.info(
            f"[FRR] Updated: total={len(records)}, latest={latest.get('date')}, "
            f"FR007={latest.get('FR007')}, FDR007={latest.get('FDR007')}"
        )
        return payload

    def _save_to_cache(self, payload: Dict[str, Any]) -> None:
        try:
            redis_client.setex(REDIS_KEY, REDIS_TTL, json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass
        _save_file_cache(payload)

    def invalidate_cache(self) -> Dict[str, Any]:
        _invalidate_cache()
        return {"success": True, "message": "Fixing repo rate cache invalidated"}

    def get_cache_status(self) -> Dict[str, Any]:
        redis_exists = False
        file_exists = FILE_CACHE.exists()
        try:
            redis_exists = redis_client.exists(REDIS_KEY) > 0
        except Exception:
            pass
        fc = _load_file_cache()
        total = len(fc.get("data", [])) if fc else 0
        return {
            "redis_cached": redis_exists,
            "file_cached": file_exists,
            "redis_key": REDIS_KEY,
            "file_cache_records": total,
        }


# シングルトンインスタンス
cn_fixing_repo_rate_service = CnFixingRepoRateService()
