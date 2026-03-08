"""
TSMC月次売上高サービス

データ項目:
- revenue: 月次売上高（百万台湾ドル）
- yoy: 前年同月比(%)
- mom: 前月比(%)

データソース:
- 過去時系列: CSV → DB蓄積（nbs_monthly_data テーブル、indicator = tsmc_revenue）
- 最新値: TWSE MOPS 公開データ API → DB蓄積
  https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv

FMPマッピング: なし

発表スケジュール: 毎月10日前後（前月の売上高を公表）
"""
import csv
import io
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
TST = ZoneInfo("Asia/Taipei")

# キャッシュ
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "tsmc_revenue_cache.json"

# CSV
CSV_DIR = Path(__file__).parent.parent.parent / "data" / "csv_import"
CSV_FILE = CSV_DIR / "TSMC収益.csv"

# DB indicator ID（nbs_monthly_data テーブルを再利用）
DB_INDICATOR = "tsmc_revenue"

# Redis
DATA_CACHE_KEY = "market:tsmc_revenue:data"

# TWSE MOPS API
MOPS_URL = "https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv"
TSMC_STOCK_CODE = "2330"


# ---------------------------------------------------------------------------
# CSV読み込み → DB蓄積
# ---------------------------------------------------------------------------

def import_csv_to_db() -> int:
    """CSVファイルからTSMC売上高データをDBにインポート

    CSV形式: 公表日,結果
    日付形式: YYYY/M（例: 2010/1）
    値形式: カンマ付き数値（例: "30,136"）単位は百万台湾ドル
    """
    from services.china.nbs_db_utils import upsert_nbs_data

    if not CSV_FILE.exists():
        logger.warning(f"[TSMCRevenue] CSV not found: {CSV_FILE}")
        return 0

    revenue_data: Dict[str, float] = {}

    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_raw = row.get("公表日", "").strip()
            value_raw = row.get("結果", "").strip().strip('"').replace(",", "")

            if not date_raw or not value_raw:
                continue

            # YYYY/M → YYYY-MM-01
            parts = date_raw.split("/")
            if len(parts) != 2:
                continue
            year, month = parts[0], parts[1].zfill(2)
            date_str = f"{year}-{month}-01"

            try:
                revenue_data[date_str] = float(value_raw)
            except ValueError:
                continue

    if revenue_data:
        count = upsert_nbs_data(DB_INDICATOR, revenue_data, source="csv")
        logger.info(f"[TSMCRevenue] CSV: {len(revenue_data)} records, DB upserted {count}")
        return count

    return 0


# ---------------------------------------------------------------------------
# TWSE MOPS API → DB蓄積
# ---------------------------------------------------------------------------

def _fetch_mops_latest() -> Optional[Dict[str, Any]]:
    """TWSE MOPS APIからTSMCの最新月次売上高を取得

    Returns:
        {'date': '2026-01-01', 'revenue': 401255} or None
        (revenue単位: 百万台湾ドル)
    """
    try:
        resp = requests.get(MOPS_URL, timeout=30)
        if resp.status_code != 200:
            logger.warning(f"[TSMCRevenue] MOPS HTTP {resp.status_code}")
            return None

        # CSVパース（BOMあり UTF-8-SIG）
        content = resp.content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))

        for row in reader:
            stock_code = row.get("公司代號", "").strip()
            if stock_code != TSMC_STOCK_CODE:
                continue

            # 資料年月: 民国年月 e.g. "11501" = 2026年01月
            data_ym = row.get("資料年月", "").strip()
            if not data_ym:
                continue

            # 民国年→西暦変換
            if len(data_ym) >= 4:
                roc_year = int(data_ym[:-2])
                month = int(data_ym[-2:])
                year = roc_year + 1911
            else:
                continue

            date_str = f"{year}-{month:02d}-01"

            # 營業收入-當月營收（単位: 千元）→ 百万元に変換
            revenue_raw = row.get("營業收入-當月營收", "").strip().replace(",", "")
            if not revenue_raw:
                continue

            try:
                revenue_thousands = float(revenue_raw)
                revenue_millions = round(revenue_thousands / 1000, 0)
            except ValueError:
                continue

            return {"date": date_str, "revenue": revenue_millions}

        logger.warning("[TSMCRevenue] TSMC (2330) not found in MOPS data")
        return None

    except Exception as e:
        logger.warning(f"[TSMCRevenue] MOPS fetch error: {e}")
        return None


def _fetch_and_upsert_latest() -> None:
    """MOPSから最新データを取得しDBに蓄積"""
    from services.china.nbs_db_utils import upsert_nbs_data

    latest = _fetch_mops_latest()
    if latest:
        count = upsert_nbs_data(
            DB_INDICATOR,
            {latest["date"]: latest["revenue"]},
            source="api",
        )
        logger.info(
            f"[TSMCRevenue] MOPS latest: {latest['date']} = {latest['revenue']:,.0f}M TWD (upserted {count})"
        )


# ---------------------------------------------------------------------------
# データ構築
# ---------------------------------------------------------------------------

def _month_to_quarter(month: int) -> int:
    """月→四半期番号 (1-3=Q1, 4-6=Q2, 7-9=Q3, 10-12=Q4)"""
    return (month - 1) // 3 + 1


def _build_data() -> Dict[str, Any]:
    """DBからデータを読み込み、月次・四半期データを構築して返す

    Returns:
        {"monthly": [...], "quarterly": [...]}
    """
    from services.china.nbs_db_utils import load_nbs_data

    # DBにデータが少ない場合はCSVインポートを実行
    raw_data = load_nbs_data(DB_INDICATOR)
    if len(raw_data) < 10:
        logger.info("[TSMCRevenue] DB has few records, importing CSV...")
        try:
            import_csv_to_db()
        except Exception as e:
            logger.warning(f"[TSMCRevenue] CSV import failed: {e}")
        raw_data = load_nbs_data(DB_INDICATOR)

    # MOPSから最新値を取得→DB蓄積（ベストエフォート）
    try:
        _fetch_and_upsert_latest()
    except Exception as e:
        logger.warning(f"[TSMCRevenue] MOPS fetch/upsert failed: {e}")

    # DBから全データ読み込み（MOPS追加分を含む）
    raw_data = load_nbs_data(DB_INDICATOR)
    logger.info(f"[TSMCRevenue] DB: {len(raw_data)} records")

    if not raw_data:
        return {"monthly": [], "quarterly": []}

    # 日付順にソート
    sorted_dates = sorted(raw_data.keys())

    # --- 月次データ構築 ---
    monthly = []
    for date_str in sorted_dates:
        revenue = raw_data[date_str]

        # YoY計算
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        prev_year_date = f"{dt.year - 1}-{dt.month:02d}-01"
        yoy = None
        if prev_year_date in raw_data and raw_data[prev_year_date] > 0:
            yoy = round(
                (revenue - raw_data[prev_year_date]) / raw_data[prev_year_date] * 100,
                2,
            )

        # MoM計算
        if dt.month == 1:
            prev_month_date = f"{dt.year - 1}-12-01"
        else:
            prev_month_date = f"{dt.year}-{dt.month - 1:02d}-01"
        mom = None
        if prev_month_date in raw_data and raw_data[prev_month_date] > 0:
            mom = round(
                (revenue - raw_data[prev_month_date]) / raw_data[prev_month_date] * 100,
                2,
            )

        monthly.append({
            "date": date_str,
            "revenue": revenue,
            "yoy": yoy,
            "mom": mom,
        })

    # --- 四半期データ構築 ---
    # Q1=1-3月, Q2=4-6月, Q3=7-9月, Q4=10-12月
    quarterly_map: Dict[str, Dict[str, Any]] = {}  # "YYYY-QN" → {...}
    for date_str in sorted_dates:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        q = _month_to_quarter(dt.month)
        q_key = f"{dt.year}-Q{q}"

        if q_key not in quarterly_map:
            quarterly_map[q_key] = {
                "year": dt.year,
                "quarter": q,
                "months_count": 0,
                "revenue": 0.0,
            }

        quarterly_map[q_key]["months_count"] += 1
        quarterly_map[q_key]["revenue"] += raw_data[date_str]

    # 四半期合計から QoQ/YoY を計算
    quarterly = []
    q_keys_sorted = sorted(quarterly_map.keys())
    q_revenue_map: Dict[str, float] = {}  # for lookups

    for q_key in q_keys_sorted:
        q_data = quarterly_map[q_key]
        year = q_data["year"]
        q = q_data["quarter"]
        revenue = round(q_data["revenue"], 0)
        months_count = q_data["months_count"]

        # 四半期末月の1日を代表日付とする（Q1=03-01, Q2=06-01, Q3=09-01, Q4=12-01）
        q_end_month = q * 3
        date_str = f"{year}-{q_end_month:02d}-01"

        q_revenue_map[q_key] = revenue

        # 不完全な四半期（3ヶ月分揃っていない）はQoQ/YoYを計算しない
        qoq = None
        yoy = None

        if months_count == 3:
            # QoQ計算
            if q == 1:
                prev_q_key = f"{year - 1}-Q4"
            else:
                prev_q_key = f"{year}-Q{q - 1}"
            if prev_q_key in q_revenue_map and q_revenue_map[prev_q_key] > 0:
                # 前四半期も3ヶ月分揃っている場合のみ
                prev_q_data = quarterly_map.get(prev_q_key, {})
                if prev_q_data.get("months_count", 0) == 3:
                    qoq = round(
                        (revenue - q_revenue_map[prev_q_key]) / q_revenue_map[prev_q_key] * 100,
                        2,
                    )

            # YoY計算
            prev_year_q_key = f"{year - 1}-Q{q}"
            if prev_year_q_key in q_revenue_map and q_revenue_map[prev_year_q_key] > 0:
                prev_yq_data = quarterly_map.get(prev_year_q_key, {})
                if prev_yq_data.get("months_count", 0) == 3:
                    yoy = round(
                        (revenue - q_revenue_map[prev_year_q_key]) / q_revenue_map[prev_year_q_key] * 100,
                        2,
                    )

        quarterly.append({
            "date": date_str,
            "quarter_label": f"{year} Q{q}",
            "revenue": revenue,
            "yoy": yoy,
            "qoq": qoq,
            "months_count": months_count,
        })

    # 不完全な四半期（3ヶ月分揃っていない）を除外
    quarterly = [q for q in quarterly if q["months_count"] == 3]

    return {"monthly": monthly, "quarterly": quarterly}


# ---------------------------------------------------------------------------
# 次回発表日
# ---------------------------------------------------------------------------

def _get_next_release() -> Optional[Dict[str, Any]]:
    """次回発表日を推定

    TSMCは毎月10日前後に前月の売上高を公表。
    """
    now = datetime.now(TST)

    # 今月10日をまだ過ぎていなければ今月10日を次回とする
    # 過ぎていれば来月10日
    if now.day < 10:
        next_date = now.replace(day=10)
    else:
        if now.month == 12:
            next_date = now.replace(year=now.year + 1, month=1, day=10)
        else:
            next_date = now.replace(month=now.month + 1, day=10)

    return {
        "date": next_date.strftime("%Y-%m-%d"),
        "label": f"TSMC Revenue ({next_date.strftime('%b')})",
    }


# ---------------------------------------------------------------------------
# サービスクラス
# ---------------------------------------------------------------------------

class TsmcRevenueService:
    """TSMC月次売上高サービス"""

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """データ取得（キャッシュ優先）"""

        if not force_refresh:
            cached = redis_client.get(DATA_CACHE_KEY)
            if cached:
                last_updated_str = cached.get("last_updated")
                if last_updated_str and not self._should_refresh(last_updated_str):
                    return {
                        "data": cached.get("data", []),
                        "quarterly": cached.get("quarterly", []),
                        "latest": cached.get("latest"),
                        "latest_quarterly": cached.get("latest_quarterly"),
                        "metadata": cached.get("metadata", {}),
                        "next_release": _get_next_release(),
                        "cached": True,
                        "source": "redis",
                        "last_updated": last_updated_str,
                    }

        # データ構築
        built = _build_data()
        monthly = built["monthly"]
        quarterly = built["quarterly"]
        latest = monthly[-1] if monthly else None
        latest_q = quarterly[-1] if quarterly else None

        if latest:
            logger.info(
                f"[TSMCRevenue] Latest: {latest['date']} = {latest['revenue']:,.0f}M TWD "
                f"(YoY: {latest.get('yoy', 'N/A')}%, MoM: {latest.get('mom', 'N/A')}%)"
            )
        if latest_q:
            logger.info(
                f"[TSMCRevenue] Latest Q: {latest_q['quarter_label']} = {latest_q['revenue']:,.0f}M TWD "
                f"(YoY: {latest_q.get('yoy', 'N/A')}%, QoQ: {latest_q.get('qoq', 'N/A')}%)"
            )

        metadata = {
            "source": "TSMC / TWSE MOPS",
            "indicator": "TSMC Monthly Revenue",
            "description": "TSMC（台湾積体電路製造）月次売上高",
            "unit": "百万台湾ドル (M TWD)",
            "frequency": "monthly",
        }

        cache_payload = {
            "data": monthly,
            "quarterly": quarterly,
            "latest": latest,
            "latest_quarterly": latest_q,
            "metadata": metadata,
            "last_updated": datetime.now(JST).isoformat(),
            "csv_mtime": self._get_csv_mtime(),
        }
        redis_client.set(DATA_CACHE_KEY, cache_payload, expire=0)
        self._save_file_cache(cache_payload)

        return {
            "data": monthly,
            "quarterly": quarterly,
            "latest": latest,
            "latest_quarterly": latest_q,
            "metadata": metadata,
            "next_release": _get_next_release(),
            "cached": False,
            "source": "db+mops",
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _should_refresh(self, last_updated_str: str) -> bool:
        """キャッシュを更新すべきか判定

        月次データ: CSVタイムスタンプ変更 or 12時間以上経過 でリフレッシュ
        """
        try:
            cached = redis_client.get(DATA_CACHE_KEY)
            if not cached:
                return True

            # CSVファイル変更チェック
            cached_csv_mtime = cached.get("csv_mtime")
            current_csv_mtime = self._get_csv_mtime()
            if cached_csv_mtime != current_csv_mtime:
                return True

            # 12時間以上経過でリフレッシュ
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            if (now - last_updated).total_seconds() > 12 * 3600:
                return True

            return False
        except Exception:
            return True

    def _get_csv_mtime(self) -> Optional[str]:
        """CSVファイルの最終更新時刻"""
        try:
            if CSV_FILE.exists():
                mtime = os.path.getmtime(CSV_FILE)
                return datetime.fromtimestamp(mtime, tz=JST).isoformat()
        except Exception:
            pass
        return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        """ファイルキャッシュ保存"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(DATA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[TSMCRevenue] File cache write error: {e}")

    def invalidate_cache(self) -> bool:
        """キャッシュ無効化"""
        return redis_client.delete(DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュ状態"""
        data_exists = redis_client.exists(DATA_CACHE_KEY)
        cached_data = redis_client.get(DATA_CACHE_KEY) if data_exists else None
        data_count = len(cached_data.get("data", [])) if cached_data else 0

        return {
            "indicator": "TSMC Monthly Revenue",
            "source": "TSMC / TWSE MOPS",
            "cache_key": DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached_data.get("last_updated") if cached_data else None,
            "data_count": data_count,
            "csv_file_exists": CSV_FILE.exists(),
            "csv_mtime": self._get_csv_mtime(),
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトン
tsmc_revenue_service = TsmcRevenueService()
