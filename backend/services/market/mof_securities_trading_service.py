"""
MOF対外対内証券売買サービス
財務省「対外及び対内証券売買等の状況」（週次）を取得し、
市場指標をオーバーレイ用にマージ

データソース:
- https://www.mof.go.jp/policy/international_policy/reference/itn_transactions_in_securities/week.csv

取得系列（Net = 取得 - 処分）:
1. 対外証券投資（居住者による取得・処分）
   - assets_equity_net: 株式・投資ファンド持分
   - assets_longterm_debt_net: 中長期債
2. 対内証券投資（非居住者による取得・処分）
   - liabilities_equity_net: 株式・投資ファンド持分
   - liabilities_longterm_debt_net: 中長期債

オーバーレイ:
- sp500: S&P 500（対外株式用）
- nikkei225: 日経平均（対外株式 + 対内株式用）
- usdjpy: ドル円（対外中長期債用）
- us10y: 米国10年債利回り（対外中長期債用）
- jgb10y: 日本10年国債利回り（対内中長期債用, FRED月次）

単位: 億円

更新スケジュール: 木・金・月の JST 8:50 → 平日 9:00 に取得
"""
import csv
import io
import json
import os
import re
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo
from pathlib import Path

from core.redis_client import redis_client


JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_CACHE_FILE = CACHE_DIR / "mof_securities_trading_cache.json"

CSV_URL = "https://www.mof.go.jp/policy/international_policy/reference/itn_transactions_in_securities/week.csv"

# FRED series for Japan 10Y government bond yield (monthly)
FRED_JGB_SERIES = "IRLTLT01JPM156N"

# CSV列の構造（Row 13 = Acquisition, Disposition, Net, ...）
# Col 0:  Period
# Col 3:  Assets Equity Net            ★
# Col 6:  Assets Long-term debt Net    ★
# Col 14: Liabilities Equity Net       ★
# Col 17: Liabilities Long-term debt Net ★


def _parse_value(s: str) -> Optional[float]:
    """CSV値をパース（カンマ区切り、空白トリムなど）"""
    s = s.strip().strip('"').strip()
    if not s or s == '-':
        return None
    cleaned = s.replace(',', '').replace(' ', '')
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_period(period_str: str) -> Optional[str]:
    """
    期間文字列からISO日付（週末日）を抽出。
    Format (cp932): "2026．3．1～3．7"
    """
    normalized = period_str
    normalized = normalized.replace('．', '.').replace('～', '~')

    clean = ''
    for ch in normalized:
        if ch.isdigit():
            clean += ch
        elif ch in '.~-/ ':
            clean += ch
        else:
            clean += '.'

    parts = re.split(r'[~`]', clean)
    year_match = re.search(r'(\d{4})', parts[0] if parts else clean)
    if not year_match:
        return None
    year = int(year_match.group(1))

    if len(parts) >= 2:
        end_part = parts[-1].strip()
        end_match = re.search(r'(\d{1,2})\D+(\d{1,2})', end_part)
        if end_match:
            month = int(end_match.group(1))
            day = int(end_match.group(2))
        else:
            nums = re.findall(r'\d+', parts[0])
            if len(nums) >= 3:
                month = int(nums[1])
                day = int(nums[2])
            else:
                return None
    else:
        nums = re.findall(r'\d+', clean)
        if len(nums) >= 5:
            month = int(nums[3])
            day = int(nums[4])
        elif len(nums) >= 3:
            month = int(nums[1])
            day = int(nums[2])
        else:
            return None

    # 年跨ぎ対応
    if len(parts) >= 2:
        start_nums = re.findall(r'\d+', parts[0])
        if len(start_nums) >= 2:
            start_month = int(start_nums[1])
            if start_month == 12 and month == 1:
                year += 1

    try:
        return f"{year}-{month:02d}-{day:02d}"
    except (ValueError, OverflowError):
        return None


def _find_closest(daily_map: Dict[str, float], date_str: str, max_delta: int = 7) -> Optional[float]:
    """日付に最も近い値をdaily_mapから検索（前後max_delta日）"""
    from datetime import date as date_cls
    try:
        dt = date_cls.fromisoformat(date_str)
    except ValueError:
        return None
    # 当日 → 前方 → 後方
    for delta in range(max_delta + 1):
        for sign in [0, -1, 1]:
            if delta == 0 and sign != 0:
                continue
            check = (dt + timedelta(days=delta * (sign if sign else 1))).isoformat()
            if check in daily_map:
                return daily_map[check]
            if delta > 0 and sign == 0:
                # 両方向を試す
                check_fwd = (dt + timedelta(days=delta)).isoformat()
                check_bwd = (dt - timedelta(days=delta)).isoformat()
                if check_fwd in daily_map:
                    return daily_map[check_fwd]
                if check_bwd in daily_map:
                    return daily_map[check_bwd]
    return None


class MofSecuritiesTradingService:
    """MOF対外対内証券売買サービス"""

    DATA_CACHE_KEY = "market:mof_securities_trading:data"
    CACHE_TTL = 6 * 3600  # 6時間

    def __init__(self):
        pass

    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """MOF対外対内証券売買データを取得"""

        if not force_refresh:
            cached = self._load_from_redis()
            if cached:
                return {
                    **cached,
                    "cached": True,
                    "source": "redis",
                }

        # CSV + オーバーレイデータを構築
        data = self._build_data()

        if data:
            self._save_to_redis(data)
            self._save_file_cache(data)
            return {
                **data,
                "cached": False,
                "source": "mof_csv + yfinance + fred",
            }

        # フォールバック: Redisキャッシュ
        cached = self._load_from_redis()
        if cached:
            return {**cached, "cached": True, "source": "redis (fallback)"}

        # フォールバック: ファイルキャッシュ
        file_cache = self._load_file_cache()
        if file_cache:
            return {**file_cache, "cached": True, "source": "file (fallback)"}

        return {
            "data": [],
            "latest": None,
            "metadata": {},
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self) -> Optional[Dict[str, Any]]:
        """MOF CSVをパースし、yfinance/FREDからオーバーレイデータをマージ"""
        # 1. MOF CSVパース
        mof_records = self._fetch_csv()
        if not mof_records:
            return None

        first_date = mof_records[0]["date"]

        # 2. yfinanceからオーバーレイデータ取得
        overlay_maps = self._fetch_yfinance_overlays(first_date)

        # 3. FREDからJGB 10Y取得
        jgb_map = self._fetch_jgb_yield(first_date)

        # 4. マージ
        for record in mof_records:
            d = record["date"]
            record["sp500"] = _find_closest(overlay_maps.get("sp500", {}), d)
            record["nikkei225"] = _find_closest(overlay_maps.get("nikkei225", {}), d)
            record["usdjpy"] = _find_closest(overlay_maps.get("usdjpy", {}), d)
            record["us10y"] = _find_closest(overlay_maps.get("us10y", {}), d)
            record["jgb10y"] = _find_closest(jgb_map, d)

        latest = mof_records[-1]

        metadata = {
            "source": "MOF + yfinance + FRED",
            "indicator": "International Transactions in Securities",
            "description": "対外及び対内証券売買等の状況（週次）",
            "unit": "億円",
            "frequency": "weekly",
            "data_count": len(mof_records),
            "start_date": mof_records[0]["date"],
            "end_date": mof_records[-1]["date"],
            "overlays": ["sp500", "nikkei225", "usdjpy", "us10y", "jgb10y"],
        }

        return {
            "data": mof_records,
            "latest": latest,
            "metadata": metadata,
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _fetch_csv(self) -> List[Dict[str, Any]]:
        """MOF CSVをダウンロードしてパース"""
        try:
            print(f"[MofSecuritiesTrading] Fetching CSV from {CSV_URL}")
            resp = requests.get(CSV_URL, timeout=30)
            resp.raise_for_status()

            text = resp.content.decode('cp932', errors='replace')
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)

            result = []
            for row_idx in range(14, len(rows)):
                row = rows[row_idx]
                if len(row) < 23:
                    continue

                period_str = row[0].strip()
                if not period_str:
                    continue

                date_str = _parse_period(period_str)
                if not date_str:
                    continue

                assets_equity_net = _parse_value(row[3])
                assets_longterm_debt_net = _parse_value(row[6])
                liabilities_equity_net = _parse_value(row[14])
                liabilities_longterm_debt_net = _parse_value(row[17])

                if all(v is None for v in [assets_equity_net, assets_longterm_debt_net,
                                           liabilities_equity_net, liabilities_longterm_debt_net]):
                    continue

                result.append({
                    "date": date_str,
                    "assets_equity_net": assets_equity_net,
                    "assets_longterm_debt_net": assets_longterm_debt_net,
                    "liabilities_equity_net": liabilities_equity_net,
                    "liabilities_longterm_debt_net": liabilities_longterm_debt_net,
                })

            result.sort(key=lambda x: x["date"])

            if result:
                print(f"[MofSecuritiesTrading] Parsed {len(result)} records "
                      f"({result[0]['date']} ~ {result[-1]['date']})")
            else:
                print("[MofSecuritiesTrading] No records parsed")

            return result

        except Exception as e:
            print(f"[MofSecuritiesTrading] Error fetching CSV: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_yfinance_overlays(self, start_date: str) -> Dict[str, Dict[str, float]]:
        """yfinanceからオーバーレイデータ（S&P500, 日経225, USDJPY, US10Y）を取得"""
        result: Dict[str, Dict[str, float]] = {
            "sp500": {},
            "nikkei225": {},
            "usdjpy": {},
            "us10y": {},
        }

        tickers = {
            "sp500": "^GSPC",
            "nikkei225": "^N225",
            "usdjpy": "USDJPY=X",
            "us10y": "^TNX",
        }

        try:
            import yfinance as yf
            for key, ticker_symbol in tickers.items():
                try:
                    ticker = yf.Ticker(ticker_symbol)
                    hist = ticker.history(start=start_date, interval="1wk")
                    if hist.empty:
                        print(f"[MofSecuritiesTrading] No data for {ticker_symbol}")
                        continue
                    hist.index = hist.index.tz_localize(None) if hist.index.tz else hist.index
                    for idx, row in hist.iterrows():
                        d = idx.strftime("%Y-%m-%d")
                        close_val = float(row["Close"])
                        if key == "us10y":
                            # ^TNX returns yield * 10 historically but recent data is direct %
                            # Ensure we store as percentage (e.g., 4.22)
                            result[key][d] = round(close_val, 3)
                        elif key in ("sp500", "nikkei225"):
                            result[key][d] = round(close_val, 2)
                        else:
                            result[key][d] = round(close_val, 3)
                    print(f"[MofSecuritiesTrading] {key}: {len(result[key])} weekly points")
                except Exception as e:
                    print(f"[MofSecuritiesTrading] yfinance error for {key}: {e}")
        except ImportError:
            print("[MofSecuritiesTrading] yfinance not available")

        return result

    def _fetch_jgb_yield(self, start_date: str) -> Dict[str, float]:
        """FREDから日本10年国債利回り(月次)を取得し、日付→利回りのマップを返す"""
        result: Dict[str, float] = {}

        fred_api_key = os.environ.get("FRED_API_KEY", "")
        if not fred_api_key:
            print("[MofSecuritiesTrading] FRED_API_KEY not set, skipping JGB 10Y")
            return result

        try:
            url = (
                f"https://api.stlouisfed.org/fred/series/observations"
                f"?series_id={FRED_JGB_SERIES}"
                f"&observation_start={start_date}"
                f"&api_key={fred_api_key}"
                f"&file_type=json"
            )
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            obs = resp.json().get("observations", [])

            if not obs:
                print("[MofSecuritiesTrading] No JGB yield data from FRED")
                return result

            # 月次データ → 日付マップ（前方充填用）
            monthly_values: List[tuple] = []
            for o in obs:
                if o["value"] != ".":
                    monthly_values.append((o["date"], float(o["value"])))

            if not monthly_values:
                return result

            # 月次 → 前方充填で日次マップを生成
            from datetime import date as date_cls
            today = date_cls.today()
            for i, (date_str, val) in enumerate(monthly_values):
                dt = date_cls.fromisoformat(date_str)
                # 次の月次データまで or 今日までフィル
                if i + 1 < len(monthly_values):
                    next_dt = date_cls.fromisoformat(monthly_values[i + 1][0])
                else:
                    next_dt = today + timedelta(days=1)
                current = dt
                while current < next_dt:
                    result[current.isoformat()] = round(val, 3)
                    current += timedelta(days=1)

            print(f"[MofSecuritiesTrading] JGB 10Y: {len(monthly_values)} monthly obs "
                  f"→ {len(result)} daily points (forward-filled)")

        except Exception as e:
            print(f"[MofSecuritiesTrading] FRED JGB fetch error: {e}")

        return result

    def _load_from_redis(self) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(self.DATA_CACHE_KEY)
            return data if data else None
        except Exception:
            return None

    def _save_to_redis(self, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(self.DATA_CACHE_KEY, data, expire=self.CACHE_TTL)
        except Exception as e:
            print(f"[MofSecuritiesTrading] Redis save error: {e}")

    def _load_file_cache(self) -> Optional[Dict[str, Any]]:
        try:
            if not DATA_CACHE_FILE.exists():
                return None
            with open(DATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def _save_file_cache(self, data: Dict[str, Any]) -> None:
        try:
            with open(DATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[MofSecuritiesTrading] File save error: {e}")

    def invalidate_cache(self) -> bool:
        return redis_client.delete(self.DATA_CACHE_KEY)

    def get_cache_status(self) -> Dict[str, Any]:
        data_exists = redis_client.exists(self.DATA_CACHE_KEY)
        cached = redis_client.get(self.DATA_CACHE_KEY) if data_exists else None

        return {
            "indicator": "MOF International Transactions in Securities",
            "source": "MOF CSV + yfinance + FRED",
            "cache_key": self.DATA_CACHE_KEY,
            "exists": data_exists,
            "last_updated": cached.get("last_updated") if cached else None,
            "data_count": len(cached.get("data", [])) if cached else 0,
            "file_cache_exists": DATA_CACHE_FILE.exists(),
        }


# シングルトンインスタンス
mof_securities_trading_service = MofSecuritiesTradingService()
