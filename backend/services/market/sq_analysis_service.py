"""
SQ/MSQ 検証分析サービス

検証対象:
- 日経225: SQ=毎月第2金曜、MSQ=3,6,9,12月の第2金曜
- S&P500: 各限月（3,6,9,12月）第3金曜

検証内容:
1. SQ/MSQ 前2営業日の騰落率
2. SQ/MSQ 当日の騰落率（イントラデイ）
3. SQ/MSQ 翌営業日の騰落率
"""
import json
import calendar
import logging
from datetime import datetime, timedelta, date, time
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yfinance as yf

from core.redis_client import redis_client
from core.database import SessionLocal
from sqlalchemy import text

logger = logging.getLogger(__name__)

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# キャッシュ設定
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "sq_analysis_cache.json"
REDIS_KEY = "market:sq_analysis:data"

# 分析対象期間
START_YEAR = 2010
END_YEAR = 2026


def _get_nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """月のn番目の特定曜日を取得 (weekday: 0=月, 4=金)"""
    first_day = date(year, month, 1)
    # 最初のweekdayまでの日数
    days_ahead = weekday - first_day.weekday()
    if days_ahead < 0:
        days_ahead += 7
    first_occurrence = first_day + timedelta(days=days_ahead)
    return first_occurrence + timedelta(weeks=n - 1)


def _is_us_dst(dt: date) -> bool:
    """米国夏時間かどうか判定（3月第2日曜〜11月第1日曜）"""
    dst_start = _get_nth_weekday(dt.year, 3, 6, 2)  # 3月第2日曜
    dst_end = _get_nth_weekday(dt.year, 11, 6, 1)    # 11月第1日曜
    return dst_start <= dt <= dst_end


def generate_sq_dates() -> Dict[str, List[Dict[str, Any]]]:
    """SQ/MSQ日付リストを生成"""
    msq_months = {3, 6, 9, 12}

    nikkei_dates = []
    sp500_dates = []

    for year in range(START_YEAR, END_YEAR + 1):
        for month in range(1, 13):
            # 未来の月はスキップ
            if date(year, month, 1) > date.today():
                break

            # 日経225: 毎月第2金曜
            sq_date = _get_nth_weekday(year, month, 4, 2)  # 4=金曜
            if sq_date <= date.today():
                is_msq = month in msq_months
                nikkei_dates.append({
                    "date": sq_date.isoformat(),
                    "year": year,
                    "month": month,
                    "type": "MSQ" if is_msq else "SQ",
                })

            # S&P500: 3,6,9,12月の第3金曜
            if month in msq_months:
                sp_sq_date = _get_nth_weekday(year, month, 4, 3)  # 第3金曜
                if sp_sq_date <= date.today():
                    sp500_dates.append({
                        "date": sp_sq_date.isoformat(),
                        "year": year,
                        "month": month,
                        "type": "SQ",
                    })

    return {
        "nikkei225": nikkei_dates,
        "sp500": sp500_dates,
    }


def _find_prev_business_days(daily_data: pd.DataFrame, target_date: str, n: int = 2) -> List[str]:
    """target_dateの前n営業日を取得"""
    dates = daily_data.index.tolist()
    date_strs = [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10] for d in dates]

    # target_dateより前の日付のみ
    prev_dates = [d for d in date_strs if d < target_date]
    return prev_dates[-n:] if len(prev_dates) >= n else prev_dates


def _find_next_business_day(daily_data: pd.DataFrame, target_date: str) -> Optional[str]:
    """target_dateの次営業日を取得"""
    dates = daily_data.index.tolist()
    date_strs = [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10] for d in dates]

    next_dates = [d for d in date_strs if d > target_date]
    return next_dates[0] if next_dates else None


def _get_close_by_date(daily_data: pd.DataFrame, date_str: str) -> Optional[float]:
    """指定日のclose値を取得"""
    for idx, row in daily_data.iterrows():
        d = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        if d == date_str:
            return float(row["Close"])
    return None


def _get_open_by_date(daily_data: pd.DataFrame, date_str: str) -> Optional[float]:
    """指定日のopen値を取得"""
    for idx, row in daily_data.iterrows():
        d = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        if d == date_str:
            return float(row["Open"])
    return None


def _calc_return(price_before: Optional[float], price_after: Optional[float]) -> Optional[float]:
    """騰落率を計算 (%)"""
    if price_before is None or price_after is None or price_before == 0:
        return None
    return round((price_after / price_before - 1) * 100, 4)


class SqAnalysisService:
    """SQ/MSQ検証分析サービス"""

    CACHE_TTL = 86400 * 7  # 7日

    def __init__(self):
        self._dukascopy_service = None
        self._ensure_table()

    def _get_dukascopy(self):
        if self._dukascopy_service is None:
            from services.market.dukascopy_service import DukascopyService
            self._dukascopy_service = DukascopyService()
        return self._dukascopy_service

    def _ensure_table(self):
        """SQ分析テーブルが無ければ作成"""
        try:
            session = SessionLocal()
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS sq_analysis (
                    symbol VARCHAR(20) NOT NULL,
                    sq_date DATE NOT NULL,
                    sq_type VARCHAR(5) NOT NULL,
                    year INT NOT NULL,
                    month INT NOT NULL,
                    sq_close DOUBLE PRECISION,
                    d_minus2_to_minus1 DOUBLE PRECISION,
                    d_minus1_to_sq DOUBLE PRECISION,
                    d_minus2_to_sq DOUBLE PRECISION,
                    sq_day_oc DOUBLE PRECISION,
                    sq_to_next DOUBLE PRECISION,
                    intraday_return DOUBLE PRECISION,
                    intraday_regular_return DOUBLE PRECISION,
                    d_minus2_date DATE,
                    d_minus1_date DATE,
                    next_date DATE,
                    intraday_open DOUBLE PRECISION,
                    intraday_close DOUBLE PRECISION,
                    intraday_regular_open DOUBLE PRECISION,
                    intraday_regular_close DOUBLE PRECISION,
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (symbol, sq_date)
                )
            """))
            session.commit()
            session.close()
        except Exception as e:
            logger.error(f"Error creating sq_analysis table: {e}")

    def _save_to_db(self, symbol: str, results: List[Dict[str, Any]]):
        """分析結果をDBに保存（UPSERT）"""
        if not results:
            return
        try:
            session = SessionLocal()
            for r in results:
                session.execute(text("""
                    INSERT INTO sq_analysis (
                        symbol, sq_date, sq_type, year, month, sq_close,
                        d_minus2_to_minus1, d_minus1_to_sq, d_minus2_to_sq,
                        sq_day_oc, sq_to_next,
                        intraday_return, intraday_regular_return,
                        d_minus2_date, d_minus1_date, next_date,
                        intraday_open, intraday_close,
                        intraday_regular_open, intraday_regular_close,
                        updated_at
                    ) VALUES (
                        :symbol, :sq_date, :sq_type, :year, :month, :sq_close,
                        :d_minus2_to_minus1, :d_minus1_to_sq, :d_minus2_to_sq,
                        :sq_day_oc, :sq_to_next,
                        :intraday_return, :intraday_regular_return,
                        :d_minus2_date, :d_minus1_date, :next_date,
                        :intraday_open, :intraday_close,
                        :intraday_regular_open, :intraday_regular_close,
                        NOW()
                    )
                    ON CONFLICT (symbol, sq_date) DO UPDATE SET
                        sq_close = EXCLUDED.sq_close,
                        d_minus2_to_minus1 = EXCLUDED.d_minus2_to_minus1,
                        d_minus1_to_sq = EXCLUDED.d_minus1_to_sq,
                        d_minus2_to_sq = EXCLUDED.d_minus2_to_sq,
                        sq_day_oc = EXCLUDED.sq_day_oc,
                        sq_to_next = EXCLUDED.sq_to_next,
                        intraday_return = COALESCE(EXCLUDED.intraday_return, sq_analysis.intraday_return),
                        intraday_regular_return = COALESCE(EXCLUDED.intraday_regular_return, sq_analysis.intraday_regular_return),
                        d_minus2_date = EXCLUDED.d_minus2_date,
                        d_minus1_date = EXCLUDED.d_minus1_date,
                        next_date = EXCLUDED.next_date,
                        intraday_open = COALESCE(EXCLUDED.intraday_open, sq_analysis.intraday_open),
                        intraday_close = COALESCE(EXCLUDED.intraday_close, sq_analysis.intraday_close),
                        intraday_regular_open = COALESCE(EXCLUDED.intraday_regular_open, sq_analysis.intraday_regular_open),
                        intraday_regular_close = COALESCE(EXCLUDED.intraday_regular_close, sq_analysis.intraday_regular_close),
                        updated_at = NOW()
                """), {
                    "symbol": symbol,
                    "sq_date": r["date"],
                    "sq_type": r.get("type", "SQ"),
                    "year": r["year"],
                    "month": r["month"],
                    "sq_close": r.get("sq_close"),
                    "d_minus2_to_minus1": r.get("d_minus2_to_minus1"),
                    "d_minus1_to_sq": r.get("d_minus1_to_sq"),
                    "d_minus2_to_sq": r.get("d_minus2_to_sq"),
                    "sq_day_oc": r.get("sq_day_oc"),
                    "sq_to_next": r.get("sq_to_next"),
                    "intraday_return": r.get("intraday_return"),
                    "intraday_regular_return": r.get("intraday_regular_return"),
                    "d_minus2_date": r.get("d_minus2_date"),
                    "d_minus1_date": r.get("d_minus1_date"),
                    "next_date": r.get("next_date"),
                    "intraday_open": r.get("intraday_open"),
                    "intraday_close": r.get("intraday_close"),
                    "intraday_regular_open": r.get("intraday_regular_open"),
                    "intraday_regular_close": r.get("intraday_regular_close"),
                })
            session.commit()
            logger.info(f"Saved {len(results)} {symbol} records to DB")
            session.close()
        except Exception as e:
            logger.error(f"Error saving to DB: {e}")

    def _load_from_db(self, symbol: str) -> List[Dict[str, Any]]:
        """DBから分析結果を読み込み"""
        try:
            session = SessionLocal()
            rows = session.execute(text("""
                SELECT sq_date, sq_type, year, month, sq_close,
                       d_minus2_to_minus1, d_minus1_to_sq, d_minus2_to_sq,
                       sq_day_oc, sq_to_next,
                       intraday_return, intraday_regular_return,
                       d_minus2_date, d_minus1_date, next_date,
                       intraday_open, intraday_close,
                       intraday_regular_open, intraday_regular_close
                FROM sq_analysis
                WHERE symbol = :symbol
                ORDER BY sq_date
            """), {"symbol": symbol}).fetchall()
            session.close()

            results = []
            for r in rows:
                entry = {
                    "date": r[0].isoformat() if r[0] else None,
                    "type": r[1],
                    "year": r[2],
                    "month": r[3],
                    "sq_close": float(r[4]) if r[4] is not None else None,
                    "d_minus2_to_minus1": float(r[5]) if r[5] is not None else None,
                    "d_minus1_to_sq": float(r[6]) if r[6] is not None else None,
                    "d_minus2_to_sq": float(r[7]) if r[7] is not None else None,
                    "sq_day_oc": float(r[8]) if r[8] is not None else None,
                    "sq_to_next": float(r[9]) if r[9] is not None else None,
                    "intraday_return": float(r[10]) if r[10] is not None else None,
                    "intraday_regular_return": float(r[11]) if r[11] is not None else None,
                    "d_minus2_date": r[12].isoformat() if r[12] else None,
                    "d_minus1_date": r[13].isoformat() if r[13] else None,
                    "next_date": r[14].isoformat() if r[14] else None,
                    "intraday_open": float(r[15]) if r[15] is not None else None,
                    "intraday_close": float(r[16]) if r[16] is not None else None,
                    "intraday_regular_open": float(r[17]) if r[17] is not None else None,
                    "intraday_regular_close": float(r[18]) if r[18] is not None else None,
                }
                results.append(entry)

            return results
        except Exception as e:
            logger.error(f"Error loading from DB: {e}")
            return []

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """SQ/MSQ分析データを取得

        優先順位: Redis → ファイルキャッシュ → DB → API取得
        """

        # キャッシュチェック
        if not force_refresh:
            cached = self._load_cache()
            if cached:
                return cached

        # SQ日付リスト生成
        sq_dates = generate_sq_dates()

        # DBからデータ読み込み
        nikkei_db = self._load_from_db("nikkei225")
        sp500_db = self._load_from_db("sp500")

        # DBに既存データがあれば、新しいSQ日のみ取得
        existing_nikkei_dates = {r["date"] for r in nikkei_db}
        existing_sp500_dates = {r["date"] for r in sp500_db}

        new_nikkei = [d for d in sq_dates["nikkei225"] if d["date"] not in existing_nikkei_dates]
        new_sp500 = [d for d in sq_dates["sp500"] if d["date"] not in existing_sp500_dates]

        # 新しいSQ日がなく、force_refreshでもない場合はDB結果を返す
        if not new_nikkei and not new_sp500 and not force_refresh and nikkei_db and sp500_db:
            logger.info(f"Loaded from DB (up to date): nikkei={len(nikkei_db)}, sp500={len(sp500_db)}")
            result = self._build_result(nikkei_db, sp500_db, source="database")
            self._save_cache(result)
            return result

        if force_refresh:
            new_nikkei = sq_dates["nikkei225"]
            new_sp500 = sq_dates["sp500"]

        # yfinance日足データ取得
        logger.info(f"Fetching daily data (new: nikkei={len(new_nikkei)}, sp500={len(new_sp500)})...")
        nikkei_daily = self._fetch_daily_yfinance("^N225")
        sp500_daily = self._fetch_daily_yfinance("^GSPC")

        # 新しいSQ日の騰落率を計算
        nikkei_new_results = self._analyze_sq_dates(new_nikkei, nikkei_daily, "nikkei225") if new_nikkei else []
        sp500_new_results = self._analyze_sq_dates(new_sp500, sp500_daily, "sp500") if new_sp500 else []

        # DBに保存
        if nikkei_new_results:
            self._save_to_db("nikkei225", nikkei_new_results)
        if sp500_new_results:
            self._save_to_db("sp500", sp500_new_results)

        # DB全体を再読み込み（既存+新規の統合済み）
        all_nikkei = self._load_from_db("nikkei225") or nikkei_new_results
        all_sp500 = self._load_from_db("sp500") or sp500_new_results

        result = self._build_result(all_nikkei, all_sp500, source="yfinance + dukascopy")

        # キャッシュ保存
        self._save_cache(result)

        return result

    def _build_result(self, nikkei_results: List[Dict], sp500_results: List[Dict], source: str) -> Dict[str, Any]:
        """結果を組み立て"""
        return {
            "nikkei225": {
                "data": nikkei_results,
                "summary": self._calc_summary(nikkei_results),
            },
            "sp500": {
                "data": sp500_results,
                "summary": self._calc_summary(sp500_results),
            },
            "cached": False,
            "source": source,
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _fetch_daily_yfinance(self, ticker: str) -> pd.DataFrame:
        """yfinanceから日足データ取得"""
        try:
            start = f"{START_YEAR}-01-01"
            end = (date.today() + timedelta(days=1)).isoformat()
            df = yf.download(ticker, start=start, end=end, progress=False)
            if df is not None and not df.empty:
                # MultiIndex columns の場合は flatten
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df
        except Exception as e:
            logger.error(f"Error fetching {ticker}: {e}")
        return pd.DataFrame()

    def _analyze_sq_dates(
        self,
        sq_dates: List[Dict],
        daily_data: pd.DataFrame,
        symbol: str,
    ) -> List[Dict[str, Any]]:
        """各SQ日の騰落率を計算"""
        if daily_data.empty:
            return []

        # まず日足ベースの騰落率を全て計算
        results = []
        for sq_info in sq_dates:
            sq_date = sq_info["date"]

            # 前2営業日
            prev_days = _find_prev_business_days(daily_data, sq_date, 2)
            # 翌営業日
            next_day = _find_next_business_day(daily_data, sq_date)

            # 各日のclose
            sq_close = _get_close_by_date(daily_data, sq_date)
            sq_open = _get_open_by_date(daily_data, sq_date)

            entry = {
                "date": sq_date,
                "year": sq_info["year"],
                "month": sq_info["month"],
                "type": sq_info["type"],
                "sq_close": sq_close,
            }

            # --- 前2営業日の騰落率 ---
            if len(prev_days) >= 2:
                d_minus2_close = _get_close_by_date(daily_data, prev_days[0])
                d_minus1_close = _get_close_by_date(daily_data, prev_days[1])
                entry["d_minus2_to_minus1"] = _calc_return(d_minus2_close, d_minus1_close)
                entry["d_minus1_to_sq"] = _calc_return(d_minus1_close, sq_close)
                entry["d_minus2_to_sq"] = _calc_return(d_minus2_close, sq_close)
                entry["d_minus2_date"] = prev_days[0]
                entry["d_minus1_date"] = prev_days[1]
            else:
                entry["d_minus2_to_minus1"] = None
                entry["d_minus1_to_sq"] = None
                entry["d_minus2_to_sq"] = None

            # --- SQ当日の日足騰落率 (open→close) ---
            entry["sq_day_oc"] = _calc_return(sq_open, sq_close)

            # --- 翌営業日の騰落率 ---
            if next_day:
                next_close = _get_close_by_date(daily_data, next_day)
                entry["sq_to_next"] = _calc_return(sq_close, next_close)
                entry["next_date"] = next_day
            else:
                entry["sq_to_next"] = None

            results.append(entry)

        # イントラデイデータを並列取得
        logger.info(f"Fetching intraday data for {len(results)} {symbol} SQ dates...")
        date_list = [r["date"] for r in results]

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self._get_intraday_return, symbol, d): i
                for i, d in enumerate(date_list)
            }
            done_count = 0
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    intraday = future.result()
                    results[idx].update(intraday)
                except Exception as e:
                    logger.error(f"Intraday error for {date_list[idx]}: {e}")
                done_count += 1
                if done_count % 20 == 0:
                    logger.info(f"  Intraday progress: {done_count}/{len(date_list)}")

        logger.info(f"  Intraday complete: {len(results)} dates")
        return results

    def _get_intraday_return(self, symbol: str, sq_date_str: str) -> Dict[str, Any]:
        """SQ当日のイントラデイ騰落率を取得"""
        result = {}
        sq_date = date.fromisoformat(sq_date_str)

        try:
            dukascopy = self._get_dukascopy()

            if symbol == "nikkei225":
                # JST 9:00-15:00 → UTC 0:00-6:00
                start_utc = datetime(sq_date.year, sq_date.month, sq_date.day, 0, 0, tzinfo=UTC)
                end_utc = datetime(sq_date.year, sq_date.month, sq_date.day, 6, 0, tzinfo=UTC)

                data = dukascopy.fetch_intraday_data(
                    "nikkei225", start_utc, end_utc, interval="5m"
                )
                if data and len(data) > 1:
                    open_price = data[0]["open"]
                    close_price = data[-1]["close"]
                    result["intraday_return"] = _calc_return(open_price, close_price)
                    result["intraday_open"] = open_price
                    result["intraday_close"] = close_price
                else:
                    result["intraday_return"] = None

            elif symbol == "sp500":
                is_dst = _is_us_dst(sq_date)

                # 正規取引時間: ET 9:30-16:00
                et_open = datetime(sq_date.year, sq_date.month, sq_date.day, 9, 30, tzinfo=ET)
                et_close = datetime(sq_date.year, sq_date.month, sq_date.day, 16, 0, tzinfo=ET)
                start_utc_regular = et_open.astimezone(UTC)
                end_utc_regular = et_close.astimezone(UTC)

                data_regular = dukascopy.fetch_intraday_data(
                    "sp500", start_utc_regular, end_utc_regular, interval="5m"
                )
                if data_regular and len(data_regular) > 1:
                    result["intraday_regular_return"] = _calc_return(
                        data_regular[0]["open"], data_regular[-1]["close"]
                    )
                    result["intraday_regular_open"] = data_regular[0]["open"]
                    result["intraday_regular_close"] = data_regular[-1]["close"]
                else:
                    result["intraday_regular_return"] = None

        except Exception as e:
            logger.error(f"Error getting intraday data for {symbol} {sq_date_str}: {e}")
            if symbol == "nikkei225":
                result["intraday_return"] = None
            else:
                result["intraday_regular_return"] = None

        return result

    def _calc_summary(self, results: List[Dict]) -> Dict[str, Any]:
        """統計サマリーを計算"""
        if not results:
            return {}

        # 全体
        all_summary = self._calc_group_stats(results, "全体")

        # SQ/MSQ別（日経のみ）
        sq_only = [r for r in results if r.get("type") == "SQ"]
        msq_only = [r for r in results if r.get("type") == "MSQ"]

        summary = {"all": all_summary}
        if sq_only:
            summary["sq"] = self._calc_group_stats(sq_only, "SQ")
        if msq_only:
            summary["msq"] = self._calc_group_stats(msq_only, "MSQ")

        # 月別サマリー
        monthly = {}
        for month in range(1, 13):
            month_data = [r for r in results if r.get("month") == month]
            if month_data:
                monthly[str(month)] = self._calc_group_stats(month_data, f"{month}月")
        summary["monthly"] = monthly

        return summary

    def _calc_group_stats(self, data: List[Dict], label: str) -> Dict[str, Any]:
        """グループの統計を計算"""
        def _stats(values: List[float], field_name: str) -> Dict:
            valid = [v for v in values if v is not None]
            if not valid:
                return {"mean": None, "median": None, "win_rate": None, "count": 0}
            s = pd.Series(valid)
            return {
                "mean": round(float(s.mean()), 4),
                "median": round(float(s.median()), 4),
                "win_rate": round(len([v for v in valid if v > 0]) / len(valid) * 100, 1),
                "count": len(valid),
            }

        stats = {
            "label": label,
            "count": len(data),
            "d_minus2_to_minus1": _stats([r.get("d_minus2_to_minus1") for r in data], "前々日→前日"),
            "d_minus1_to_sq": _stats([r.get("d_minus1_to_sq") for r in data], "前日→SQ日"),
            "d_minus2_to_sq": _stats([r.get("d_minus2_to_sq") for r in data], "前2日間"),
            "sq_day_oc": _stats([r.get("sq_day_oc") for r in data], "SQ当日(始値→終値)"),
            "sq_to_next": _stats([r.get("sq_to_next") for r in data], "SQ→翌営業日"),
        }

        # イントラデイ（日経）
        intraday_vals = [r.get("intraday_return") for r in data if r.get("intraday_return") is not None]
        if intraday_vals:
            stats["intraday_return"] = _stats(intraday_vals, "当日イントラデイ")

        # イントラデイ（S&P500 正規）
        regular_vals = [r.get("intraday_regular_return") for r in data if r.get("intraday_regular_return") is not None]
        if regular_vals:
            stats["intraday_regular_return"] = _stats(regular_vals, "正規取引時間")

        return stats

    def _load_cache(self) -> Optional[Dict]:
        """キャッシュからデータをロード"""
        # Redis
        cached = redis_client.get(REDIS_KEY)
        if cached:
            return cached

        # ファイル
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Redisにも保存
                redis_client.set(REDIS_KEY, data, expire=self.CACHE_TTL)
                return data
            except Exception as e:
                logger.error(f"Error loading cache: {e}")

        return None

    def _save_cache(self, data: Dict):
        """キャッシュにデータを保存"""
        try:
            redis_client.set(REDIS_KEY, data, expire=self.CACHE_TTL)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
