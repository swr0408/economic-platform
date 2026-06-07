"""
中国 Central Parity Rate（基準値・Fixing）サービス

データソース:
  - 過去データ: backend/data/csv_import/Central_Parity_Historical_Data_{yyyy}.xlsx
  - 最新データ: chinamoney.com.cn API（毎日当年ファイルを更新）
  - 市場レート: yfinance (CNY=X) USD/CNYスポットレート

対象系列:
  USD/CNY（メイン系列）+ yfinance USD/CNY スポットレート

Excelファイル構造:
  Row 0: ヘッダー ['Date', 'USD/CNY']
  Row 1+: データ行 ('06 Mar 2026', '6.9025')
  最終2行: フッター ('Data source:', ...) - スキップ

API:
  URL: https://www.chinamoney.com.cn/ags/ms/cm-u-bk-ccpr/CcprHisNew
  Method: GET
  Params: lang=EN&startDate=01 Jan 2026&endDate=07 Mar 2026
  Response: records[].date ('06 Mar 2026'), records[].values[0] (USD/CNY)

更新方式:
  毎日 17:00 JST（16:00 CST）: 当年 API 取得 → 当年 Excel 上書き → Redis キャッシュ再構築

キャッシュ: Redis TTL 6時間 + ファイルキャッシュ（フォールバック）
"""
import json
import time
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from core.redis_client import redis_client

logger = logging.getLogger("cn_central_parity_service")

JST = ZoneInfo("Asia/Tokyo")

# キャッシュ設定
REDIS_KEY = "china:cn_central_parity:data"
REDIS_TTL = 6 * 3600  # 6時間

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "china" / "policy"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
FILE_CACHE = CACHE_DIR / "cn_central_parity_cache.json"

# Excel ディレクトリ（csv_importに過去データがある）
EXCEL_DIR = Path(__file__).parent.parent.parent / "data" / "csv_import"

# API設定
API_URL = "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-ccpr/CcprHisNew"
API_HEADERS = {
    "Referer": "https://www.chinamoney.com.cn/english/bmkcpr/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
}

# Excelファイル開始年
EXCEL_START_YEAR = 2016

# USD/CNY は values 配列の先頭（index 0）
USDCNY_INDEX = 0


# =============================================================================
# Excel 読み込み
# =============================================================================

def _excel_path(year: int) -> Path:
    return EXCEL_DIR / f"Central_Parity_Historical_Data_{year}.xlsx"


def _read_excel_year(year: int) -> List[Dict[str, Any]]:
    """指定年のExcelを読み込んでレコードリストを返す"""
    path = _excel_path(year)
    if not path.exists():
        return []

    try:
        df = pd.read_excel(path, header=None)
    except Exception as e:
        logger.error(f"[CentralParity] Excel read error ({year}): {e}")
        return []

    records = []
    for i in range(1, len(df)):  # Row 0 はヘッダー
        row = df.iloc[i]
        date_raw = row.iloc[0]
        # フッター行スキップ
        if pd.isna(date_raw) or str(date_raw).strip().startswith("Data source"):
            continue
        try:
            dt = datetime.strptime(str(date_raw).strip(), "%d %b %Y").date()
            date_str = dt.isoformat()
        except ValueError:
            continue

        # USD/CNY値を取得（列1）
        raw = row.iloc[1] if len(row) > 1 else None
        try:
            value = float(raw) if raw is not None and not pd.isna(raw) else None
        except (ValueError, TypeError):
            value = None

        if value is not None:
            records.append({"date": date_str, "fixing": value})

    return records


def _load_all_excel() -> List[Dict[str, Any]]:
    """全年Excelを読み込んで昇順に結合して返す"""
    current_year = date.today().year
    all_records: Dict[str, Dict[str, Any]] = {}

    for year in range(EXCEL_START_YEAR, current_year + 1):
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
    """指定年のデータを API から取得して返す"""
    start = date(year, 1, 1)
    end = min(date(year, 12, 31), date.today())

    all_records: List[Dict[str, Any]] = []

    # APIは1回で最大数百件返す。ページネーション対応
    # 注: 2026-04頃からGETは403を返すようになったためPOSTで送信する
    page = 1
    while True:
        payload = {
            "lang": "EN",
            "startDate": _date_to_api_fmt(start),
            "endDate": _date_to_api_fmt(end),
            "pageNum": page,
            "pageSize": 300,
        }
        try:
            resp = requests.post(API_URL, data=payload, headers=API_HEADERS, timeout=30)
            resp.raise_for_status()
            api_data = resp.json()
        except Exception as e:
            logger.error(f"[CentralParity] API error (year={year}, page={page}): {e}")
            break

        records_raw = api_data.get("records", [])
        if not records_raw:
            break

        for rec in records_raw:
            date_raw = rec.get("date")
            if not date_raw:
                continue
            try:
                dt = datetime.strptime(date_raw.strip(), "%d %b %Y").date()
                date_str = dt.isoformat()
            except ValueError:
                continue

            values = rec.get("values", [])
            if not values:
                continue
            try:
                fixing = float(values[USDCNY_INDEX])
            except (ValueError, TypeError, IndexError):
                continue

            all_records.append({"date": date_str, "fixing": fixing})

        # ページネーションチェック
        data_meta = api_data.get("data", {})
        total = data_meta.get("total", 0)
        page_total = data_meta.get("pageTotal", 1)
        if page >= page_total:
            break
        page += 1

    all_records.sort(key=lambda x: x["date"])
    return all_records


def _save_year_to_excel(year: int, records: List[Dict[str, Any]]) -> None:
    """既存Excelとマージして当年Excelを上書き保存"""
    path = _excel_path(year)

    existing = {r["date"]: r for r in _read_excel_year(year)}
    for row in records:
        existing[row["date"]] = row

    sorted_rows = sorted(existing.values(), key=lambda x: x["date"], reverse=True)

    rows_for_df = []
    for row in sorted_rows:
        rows_for_df.append([
            datetime.strptime(row["date"], "%Y-%m-%d").strftime("%d %b %Y"),
            str(row.get("fixing") or ""),
        ])

    header = [["Date", "USD/CNY"]]
    footer = [
        ["Data source:", "China Foreign Exchange Trade System (CFETS)"],
        ["", "www.chinamoney.com.cn/english/"],
    ]

    df = pd.DataFrame(header + rows_for_df + footer)
    try:
        df.to_excel(path, index=False, header=False)
        logger.info(f"[CentralParity] Saved {len(rows_for_df)} rows to {path.name}")
    except Exception as e:
        logger.error(f"[CentralParity] Excel write error ({year}): {e}")


# =============================================================================
# yfinance USD/CNY スポットレート取得
# =============================================================================

def _fetch_usdcny_spot() -> List[Dict[str, Any]]:
    """yfinance から USD/CNY スポットレートを取得（過去最大期間）"""
    try:
        import yfinance as yf
        ticker = yf.Ticker("CNY=X")
        hist = ticker.history(period="max")
        records = []
        for idx, row in hist.iterrows():
            date_str = idx.strftime("%Y-%m-%d")
            close = row.get("Close")
            if close is not None and not pd.isna(close):
                records.append({"date": date_str, "spot": round(float(close), 4)})
        records.sort(key=lambda x: x["date"])
        return records
    except Exception as e:
        logger.error(f"[CentralParity] yfinance error: {e}")
        return []


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

def _build_payload(fixing_records: List[Dict[str, Any]],
                   spot_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """FixingとSpotをdate基準でマージしてペイロードを構築"""
    # スポットをdateでインデックス化
    spot_map: Dict[str, float] = {}
    for rec in spot_records:
        spot_map[rec["date"]] = rec["spot"]

    merged: List[Dict[str, Any]] = []
    for rec in fixing_records:
        entry: Dict[str, Any] = {
            "date": rec["date"],
            "fixing": rec["fixing"],
            "spot": spot_map.get(rec["date"]),
        }
        merged.append(entry)

    # スポットのみの日付を追加（Fixingがない日、土日のスポットは除外）
    fixing_dates = {r["date"] for r in fixing_records}
    for rec in spot_records:
        if rec["date"] not in fixing_dates:
            merged.append({
                "date": rec["date"],
                "fixing": None,
                "spot": rec["spot"],
            })

    merged.sort(key=lambda x: x["date"])

    # 最新値（fixingがある最新レコード）
    latest_fixing = None
    for rec in reversed(merged):
        if rec.get("fixing") is not None:
            latest_fixing = rec
            break

    latest_spot = None
    for rec in reversed(merged):
        if rec.get("spot") is not None:
            latest_spot = rec
            break

    return {
        "data": merged,
        "latest": {
            "fixing_date": latest_fixing["date"] if latest_fixing else None,
            "fixing": latest_fixing["fixing"] if latest_fixing else None,
            "spot_date": latest_spot["date"] if latest_spot else None,
            "spot": latest_spot["spot"] if latest_spot else None,
        },
        "metadata": {
            "source": "China Foreign Exchange Trade System (CFETS) / Yahoo Finance",
            "unit": "CNY per USD",
            "frequency": "daily",
            "series": ["fixing", "spot"],
            "total_records": len(merged),
        },
    }


# =============================================================================
# メインサービスクラス
# =============================================================================

class CnCentralParityService:
    """
    中国 Central Parity Rate (USD/CNY Fixing) サービス

    - 全年 Excel を読み込んで時系列データを提供
    - yfinance USD/CNY スポットレートを重ねて表示
    - 毎日: 当年 API 取得 → 当年 Excel 上書き → キャッシュ再構築
    """

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Central Parity + USD/CNY スポットの時系列データを返す"""
        if not force_refresh:
            try:
                cached = redis_client.get(REDIS_KEY)
                if cached:
                    return json.loads(cached) if isinstance(cached, str) else cached
            except Exception:
                pass
            fc = _load_file_cache()
            if fc:
                return fc

        fixing_records = _load_all_excel()
        spot_records = _fetch_usdcny_spot()

        if not fixing_records and not spot_records:
            fc = _load_file_cache()
            if fc:
                return fc
            return {"data": [], "latest": None, "metadata": {}}

        payload = _build_payload(fixing_records, spot_records)
        self._save_to_cache(payload)
        return payload

    def update_current_year(self) -> Dict[str, Any]:
        """
        当年データを API から取得 → 当年 Excel 上書き → キャッシュ再構築

        毎日 16:00 CST 以降に呼び出す差分更新メソッド。
        """
        current_year = date.today().year

        api_records = _fetch_year_from_api(current_year)
        if not api_records:
            logger.warning(f"[CentralParity] API returned no records for {current_year}")
            return self.get_data()

        _save_year_to_excel(current_year, api_records)
        _invalidate_cache()

        fixing_records = _load_all_excel()
        spot_records = _fetch_usdcny_spot()
        payload = _build_payload(fixing_records, spot_records)
        self._save_to_cache(payload)

        latest = payload.get("latest") or {}
        logger.info(
            f"[CentralParity] Updated: total={len(fixing_records)}, "
            f"latest_fixing={latest.get('fixing_date')}, "
            f"fixing={latest.get('fixing')}, spot={latest.get('spot')}"
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
        return {"success": True, "message": "Central Parity cache invalidated"}

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
cn_central_parity_service = CnCentralParityService()
