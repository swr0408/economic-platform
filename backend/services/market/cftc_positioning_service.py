"""
CFTC Positioning サービス

データソース:
  - DB: cftc_disagg_positions (コモディティ6銘柄), cftc_tff_positions (金融19銘柄)
  - 最新値更新: CFTC PRE API (毎週金曜リリース)
  - 価格データ: yfinance

更新: 12時間TTL (Redis + ファイル)
"""

import io
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "market"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ===== Asset Definitions =====

DISAGG_ASSETS = {
    "088691": "gold",
    "084691": "silver",
    "085692": "copper",
    "067651": "crude_oil",
    "06765T": "brent",
    "023651": "natural_gas",
}
DISAGG_ASSETS_REVERSE = {v: k for k, v in DISAGG_ASSETS.items()}

TFF_ASSETS = {
    "232741": "audusd",
    "099741": "eurusd",
    "096742": "gbpusd",
    "112741": "nzdusd",
    "090741": "usdcad",
    "092741": "usdchf",
    "097741": "usdjpy",
    "098662": "usd_index",
    "13874+": "sp500",
    "12460+": "dow",
    "20974+": "nasdaq100",
    "239742": "russell2000",
    "240741": "nikkei225",
    "042601": "us02y",
    "043602": "us10y",
    "020601": "us30y",
    "1170E1": "vix",
    "399741": "eurjpy",
    "299741": "eurgbp",
}
TFF_ASSETS_REVERSE = {v: k for k, v in TFF_ASSETS.items()}

ALL_ASSETS = {**{v: "disagg" for v in DISAGG_ASSETS.values()},
              **{v: "tff" for v in TFF_ASSETS.values()}}

ASSET_LABELS = {
    "gold": "金（ゴールド）",
    "silver": "銀（シルバー）",
    "copper": "銅（カッパー）",
    "crude_oil": "原油（WTI）",
    "brent": "ブレント原油",
    "natural_gas": "天然ガス",
    "audusd": "豪ドル/米ドル",
    "eurusd": "ユーロ/米ドル",
    "gbpusd": "英ポンド/米ドル",
    "nzdusd": "NZドル/米ドル",
    "usdcad": "米ドル/カナダドル",
    "usdchf": "米ドル/スイスフラン",
    "usdjpy": "米ドル/円",
    "usd_index": "ドルインデックス",
    "sp500": "S&P 500",
    "dow": "ダウ平均",
    "nasdaq100": "ナスダック100",
    "russell2000": "ラッセル2000",
    "nikkei225": "日経225",
    "us02y": "米国2年債",
    "us10y": "米国10年債",
    "us30y": "米国30年債",
    "vix": "VIX",
    "eurjpy": "ユーロ/円",
    "eurgbp": "ユーロ/ポンド",
}

YFINANCE_SYMBOLS = {
    "gold": "GC=F",
    "silver": "SI=F",
    "copper": "HG=F",
    "crude_oil": "CL=F",
    "brent": "BZ=F",
    "natural_gas": "NG=F",
    "sp500": "^GSPC",
    "dow": "^DJI",
    "nasdaq100": "^NDX",
    "russell2000": "^RUT",
    "nikkei225": "^N225",
    "us02y": "2YY=F",
    "us10y": "^TNX",
    "us30y": "^TYX",
    "vix": "^VIX",
    "usdjpy": "JPY=X",
    "eurusd": "EURUSD=X",
    "gbpusd": "GBPUSD=X",
    "audusd": "AUDUSD=X",
    "nzdusd": "NZDUSD=X",
    "usdcad": "USDCAD=X",
    "usdchf": "USDCHF=X",
    "usd_index": "DX-Y.NYB",
    "eurjpy": "EURJPY=X",
    "eurgbp": "EURGBP=X",
}

DISAGG_API_URL = "https://publicreporting.cftc.gov/api/views/72hh-3qpy/rows.csv?accessType=DOWNLOAD"
TFF_API_URL = "https://publicreporting.cftc.gov/api/views/gpe5-46if/rows.csv?accessType=DOWNLOAD"
LEGACY_API_URL = "https://publicreporting.cftc.gov/api/views/6dca-aqww/rows.csv?accessType=DOWNLOAD"


class CftcPositioningService:
    """CFTC建玉報告サービス（全25銘柄統合）"""

    def _cache_key(self, asset: str) -> str:
        return f"market:cftc_positioning:{asset}:data"

    def _cache_file(self, asset: str) -> Path:
        return CACHE_DIR / f"cftc_positioning_{asset}_cache.json"

    def _should_refresh(self, asset: str) -> bool:
        try:
            cached = redis_client.get(self._cache_key(asset))
            if not cached:
                return True
            last_updated_str = cached.get("last_updated")
            if not last_updated_str:
                return True
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now(JST)
            if (now - last_updated).total_seconds() < 12 * 3600:
                return False
            return True
        except Exception:
            return True

    def get_available_assets(self) -> List[Dict[str, str]]:
        """利用可能な銘柄一覧"""
        result = []
        for asset_name, report_type in ALL_ASSETS.items():
            result.append({
                "asset": asset_name,
                "label": ASSET_LABELS.get(asset_name, asset_name),
                "report_type": report_type,
            })
        return result

    def get_data(self, asset: str, force_refresh: bool = False) -> Dict[str, Any]:
        """指定銘柄のCFTCポジションデータを取得"""
        if asset not in ALL_ASSETS:
            return {
                "data": [],
                "latest": None,
                "metadata": {"error": f"Unknown asset: {asset}"},
                "cached": False,
                "source": "error",
                "last_updated": None,
            }

        if not force_refresh and not self._should_refresh(asset):
            cached = self._load_from_redis(asset)
            if cached and cached.get("data"):
                return cached

        try:
            data = self._build_data(asset)
            if data and data.get("data"):
                self._save_to_cache(asset, data)
                return data
        except Exception as e:
            logger.error(f"[CftcPositioning] Build error for {asset}: {e}")
            import traceback
            traceback.print_exc()

        cached = self._load_from_redis(asset)
        if cached and cached.get("data"):
            return cached

        cached = self._load_from_file(asset)
        if cached and cached.get("data"):
            return cached

        report_type = ALL_ASSETS.get(asset, "unknown")
        return {
            "data": [],
            "latest": None,
            "metadata": {
                "asset": asset,
                "report_type": report_type,
                "source": f"CFTC {report_type.upper()} COT",
            },
            "cached": False,
            "source": "error",
            "last_updated": None,
        }

    def _build_data(self, asset: str) -> Optional[Dict[str, Any]]:
        """DBからデータ構築 + yfinance価格結合"""
        from core.database import SessionLocal
        from sqlalchemy import text

        report_type = ALL_ASSETS[asset]

        with SessionLocal() as session:
            if report_type == "disagg":
                rows = self._query_disagg(session, asset)
            else:
                rows = self._query_tff(session, asset)

        if not rows:
            logger.warning(f"[CftcPositioning] No DB data for {asset}")
            return None

        # Fetch price data from yfinance
        price_map = self._fetch_price_data(asset)

        # Build unified response
        result_data = []
        for row in rows:
            date_str = row["date"]
            entry = {
                "date": date_str,
                "open_interest": row.get("open_interest"),
                "spec_long": row["spec_long"],
                "spec_short": row["spec_short"],
                "spec_net": row["spec_net"],
                "comm_long": row["comm_long"],
                "comm_short": row["comm_short"],
                "comm_net": row["comm_net"],
                "price": price_map.get(date_str),
            }
            result_data.append(entry)

        # Find latest with non-null spec_net
        latest = None
        for entry in reversed(result_data):
            if entry.get("spec_net") is not None:
                latest = entry.copy()
                break

        return {
            "data": result_data,
            "latest": latest,
            "metadata": {
                "asset": asset,
                "asset_label": ASSET_LABELS.get(asset, asset),
                "report_type": report_type,
                "source": "CFTC Legacy COT",
                "frequency": "weekly",
                "unit": "contracts",
                "data_count": len(result_data),
                "start_date": result_data[0]["date"] if result_data else None,
                "end_date": result_data[-1]["date"] if result_data else None,
            },
            "cached": False,
            "source": "model",
            "last_updated": datetime.now(JST).isoformat(),
        }

    def _query_disagg(self, session, asset: str) -> List[Dict]:
        """DisAgg テーブルから Legacy相当の Non-Commercial/Commercial を算出
        Non-Commercial = Managed Money + Other Reportables
        Commercial = Producer/Merchant + Swap Dealer
        """
        from sqlalchemy import text

        asset_code = DISAGG_ASSETS_REVERSE.get(asset)
        if not asset_code:
            return []

        result = session.execute(text("""
            SELECT date, open_interest,
                   mm_long, mm_short, mm_spread,
                   pm_long, pm_short,
                   swap_long, swap_short, swap_spread,
                   other_long, other_short, other_spread,
                   nonrept_long, nonrept_short
            FROM cftc_disagg_positions
            WHERE asset_code = :code
            ORDER BY date ASC
        """), {"code": asset_code})

        rows = []
        for r in result:
            mm_long = r[2] or 0
            mm_short = r[3] or 0
            pm_long = r[5] or 0
            pm_short = r[6] or 0
            swap_long = r[7] or 0
            swap_short = r[8] or 0
            swap_spread = r[9] or 0
            other_long = r[10] or 0
            other_short = r[11] or 0

            # Legacy Non-Commercial = Managed Money + Other Reportables
            spec_long = mm_long + other_long
            spec_short = mm_short + other_short
            spec_net = spec_long - spec_short

            # Legacy Commercial = Producer/Merchant + Swap Dealer (long/short include spread)
            comm_long = pm_long + swap_long + swap_spread
            comm_short = pm_short + swap_short + swap_spread
            comm_net = comm_long - comm_short

            rows.append({
                "date": r[0].strftime("%Y-%m-%d"),
                "open_interest": r[1],
                "spec_long": spec_long,
                "spec_short": spec_short,
                "spec_net": spec_net,
                "comm_long": comm_long,
                "comm_short": comm_short,
                "comm_net": comm_net,
            })
        return rows

    def _query_tff(self, session, asset: str) -> List[Dict]:
        """Legacy テーブルから Non-Commercial/Commercial を取得"""
        from sqlalchemy import text

        asset_code = TFF_ASSETS_REVERSE.get(asset)
        if not asset_code:
            return []

        result = session.execute(text("""
            SELECT date, open_interest,
                   noncomm_long, noncomm_short, noncomm_net,
                   comm_long, comm_short, comm_net
            FROM cftc_legacy_positions
            WHERE asset_code = :code
            ORDER BY date ASC
        """), {"code": asset_code})

        rows = []
        for r in result:
            rows.append({
                "date": r[0].strftime("%Y-%m-%d"),
                "open_interest": r[1],
                "spec_long": r[2],    # Non-Commercial Long
                "spec_short": r[3],   # Non-Commercial Short
                "spec_net": r[4],     # Non-Commercial Net
                "comm_long": r[5],    # Commercial Long
                "comm_short": r[6],   # Commercial Short
                "comm_net": r[7],     # Commercial Net
            })
        return rows

    def _fetch_price_data(self, asset: str) -> Dict[str, float]:
        """yfinanceから価格データ取得し date→close のマップを返す"""
        import yfinance as yf

        symbol = YFINANCE_SYMBOLS.get(asset)
        if not symbol:
            return {}

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="max")
            if hist.empty:
                return {}

            price_map = {}
            for idx, row in hist.iterrows():
                date_str = idx.strftime("%Y-%m-%d")
                price_map[date_str] = round(float(row["Close"]), 4)

            # Also fill weekly gaps: for each CFTC date, find nearest prior trading day
            return price_map
        except Exception as e:
            logger.warning(f"[CftcPositioning] yfinance error for {asset} ({symbol}): {e}")
            return {}

    def update_latest_disagg(self) -> int:
        """CFTC DisAgg APIから最新データを取得しDBに追記"""
        import requests
        from core.database import SessionLocal
        from sqlalchemy import text

        try:
            logger.info("[CftcPositioning] Downloading DisAgg latest data ...")
            resp = requests.get(DISAGG_API_URL, timeout=300)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
        except Exception as e:
            logger.error(f"[CftcPositioning] DisAgg API error: {e}")
            return 0

        df["CFTC_Contract_Market_Code"] = df["CFTC_Contract_Market_Code"].astype(str).str.strip()

        # Get latest date per asset in DB
        with SessionLocal() as session:
            result = session.execute(text(
                "SELECT asset_code, MAX(date) FROM cftc_disagg_positions GROUP BY asset_code"
            ))
            db_latest = {row[0]: row[1] for row in result}

        df_filtered = df[df["CFTC_Contract_Market_Code"].isin(DISAGG_ASSETS.keys())]
        count = 0

        with SessionLocal() as session:
            for _, row in df_filtered.iterrows():
                asset_code = row["CFTC_Contract_Market_Code"]
                asset_name = DISAGG_ASSETS[asset_code]

                date_val = row.get("Report_Date_as_MM_DD_YYYY")
                if pd.isna(date_val):
                    continue
                date_parsed = pd.to_datetime(date_val)
                date_str = date_parsed.strftime("%Y-%m-%d")
                report_date = date_parsed.date()

                # Skip if already in DB
                existing_max = db_latest.get(asset_code)
                if existing_max and report_date <= existing_max:
                    continue

                mm_long = self._sf(row.get("M_Money_Positions_Long_ALL"))
                mm_short = self._sf(row.get("M_Money_Positions_Short_ALL"))
                mm_spread = self._sf(row.get("M_Money_Positions_Spread_ALL"))
                mm_net = (mm_long - mm_short) if mm_long is not None and mm_short is not None else None

                pm_long = self._sf(row.get("Prod_Merc_Positions_Long_ALL"))
                pm_short = self._sf(row.get("Prod_Merc_Positions_Short_ALL"))
                pm_net = (pm_long - pm_short) if pm_long is not None and pm_short is not None else None

                swap_long = self._sf(row.get("Swap_Positions_Long_All"))
                swap_short = self._sf(row.get("Swap__Positions_Short_All", row.get("Swap_Positions_Short_All")))
                swap_spread = self._sf(row.get("Swap__Positions_Spread_All", row.get("Swap_Positions_Spread_All")))
                swap_net = (swap_long - swap_short) if swap_long is not None and swap_short is not None else None

                other_long = self._sf(row.get("Other_Rept_Positions_Long_ALL"))
                other_short = self._sf(row.get("Other_Rept_Positions_Short_ALL"))
                other_spread = self._sf(row.get("Other_Rept_Positions_Spread_ALL"))
                other_net = (other_long - other_short) if other_long is not None and other_short is not None else None

                nonrept_long = self._sf(row.get("NonRept_Positions_Long_All"))
                nonrept_short = self._sf(row.get("NonRept_Positions_Short_All"))
                nonrept_net = (nonrept_long - nonrept_short) if nonrept_long is not None and nonrept_short is not None else None

                session.execute(text("""
                    INSERT INTO cftc_disagg_positions (
                        date, asset_code, asset_name, open_interest,
                        mm_long, mm_short, mm_spread, mm_net,
                        pm_long, pm_short, pm_net,
                        swap_long, swap_short, swap_spread, swap_net,
                        other_long, other_short, other_spread, other_net,
                        nonrept_long, nonrept_short, nonrept_net
                    ) VALUES (
                        :date, :asset_code, :asset_name, :oi,
                        :mm_long, :mm_short, :mm_spread, :mm_net,
                        :pm_long, :pm_short, :pm_net,
                        :swap_long, :swap_short, :swap_spread, :swap_net,
                        :other_long, :other_short, :other_spread, :other_net,
                        :nonrept_long, :nonrept_short, :nonrept_net
                    )
                    ON CONFLICT (date, asset_code) DO UPDATE SET
                        mm_long = EXCLUDED.mm_long, mm_short = EXCLUDED.mm_short,
                        mm_spread = EXCLUDED.mm_spread, mm_net = EXCLUDED.mm_net,
                        pm_long = EXCLUDED.pm_long, pm_short = EXCLUDED.pm_short, pm_net = EXCLUDED.pm_net,
                        swap_long = EXCLUDED.swap_long, swap_short = EXCLUDED.swap_short,
                        swap_spread = EXCLUDED.swap_spread, swap_net = EXCLUDED.swap_net,
                        other_long = EXCLUDED.other_long, other_short = EXCLUDED.other_short,
                        other_spread = EXCLUDED.other_spread, other_net = EXCLUDED.other_net,
                        nonrept_long = EXCLUDED.nonrept_long, nonrept_short = EXCLUDED.nonrept_short,
                        nonrept_net = EXCLUDED.nonrept_net,
                        updated_at = NOW()
                """), {
                    "date": date_str, "asset_code": asset_code, "asset_name": asset_name,
                    "oi": self._sf(row.get("Open_Interest_All")),
                    "mm_long": mm_long, "mm_short": mm_short, "mm_spread": mm_spread, "mm_net": mm_net,
                    "pm_long": pm_long, "pm_short": pm_short, "pm_net": pm_net,
                    "swap_long": swap_long, "swap_short": swap_short, "swap_spread": swap_spread, "swap_net": swap_net,
                    "other_long": other_long, "other_short": other_short, "other_spread": other_spread, "other_net": other_net,
                    "nonrept_long": nonrept_long, "nonrept_short": nonrept_short, "nonrept_net": nonrept_net,
                })
                count += 1

            session.commit()

        logger.info(f"[CftcPositioning] DisAgg updated: {count} new rows")
        return count

    def update_latest_tff(self) -> int:
        """CFTC TFF APIから最新データを取得しDBに追記"""
        import requests
        from core.database import SessionLocal
        from sqlalchemy import text

        try:
            logger.info("[CftcPositioning] Downloading TFF latest data ...")
            resp = requests.get(TFF_API_URL, timeout=300)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
        except Exception as e:
            logger.error(f"[CftcPositioning] TFF API error: {e}")
            return 0

        df["CFTC_Contract_Market_Code"] = df["CFTC_Contract_Market_Code"].astype(str).str.strip()

        with SessionLocal() as session:
            result = session.execute(text(
                "SELECT asset_code, MAX(date) FROM cftc_tff_positions GROUP BY asset_code"
            ))
            db_latest = {row[0]: row[1] for row in result}

        df_filtered = df[df["CFTC_Contract_Market_Code"].isin(TFF_ASSETS.keys())]
        count = 0

        with SessionLocal() as session:
            for _, row in df_filtered.iterrows():
                asset_code = row["CFTC_Contract_Market_Code"]
                asset_name = TFF_ASSETS[asset_code]

                date_raw = row.get("Report_Date_as_YYYY_MM_DD")
                if pd.isna(date_raw):
                    continue
                try:
                    date_parsed = pd.to_datetime(date_raw)
                    date_str = date_parsed.strftime("%Y-%m-%d")
                    report_date = date_parsed.date()
                except Exception:
                    continue

                existing_max = db_latest.get(asset_code)
                if existing_max and report_date <= existing_max:
                    continue

                dealer_long = self._sf(row.get("Dealer_Positions_Long_All"))
                dealer_short = self._sf(row.get("Dealer_Positions_Short_All"))
                dealer_spread = self._sf(row.get("Dealer_Positions_Spread_All"))
                dealer_net = (dealer_long - dealer_short) if dealer_long is not None and dealer_short is not None else None

                asset_mgr_long = self._sf(row.get("Asset_Mgr_Positions_Long_All"))
                asset_mgr_short = self._sf(row.get("Asset_Mgr_Positions_Short_All"))
                asset_mgr_spread = self._sf(row.get("Asset_Mgr_Positions_Spread_All"))
                asset_mgr_net = (asset_mgr_long - asset_mgr_short) if asset_mgr_long is not None and asset_mgr_short is not None else None

                lev_money_long = self._sf(row.get("Lev_Money_Positions_Long_All"))
                lev_money_short = self._sf(row.get("Lev_Money_Positions_Short_All"))
                lev_money_spread = self._sf(row.get("Lev_Money_Positions_Spread_All"))
                lev_money_net = (lev_money_long - lev_money_short) if lev_money_long is not None and lev_money_short is not None else None

                other_long = self._sf(row.get("Other_Rept_Positions_Long_All"))
                other_short = self._sf(row.get("Other_Rept_Positions_Short_All"))
                other_spread = self._sf(row.get("Other_Rept_Positions_Spread_All"))
                other_net = (other_long - other_short) if other_long is not None and other_short is not None else None

                nonrept_long = self._sf(row.get("NonRept_Positions_Long_All"))
                nonrept_short = self._sf(row.get("NonRept_Positions_Short_All"))
                nonrept_net = (nonrept_long - nonrept_short) if nonrept_long is not None and nonrept_short is not None else None

                session.execute(text("""
                    INSERT INTO cftc_tff_positions (
                        date, asset_code, asset_name, open_interest,
                        dealer_long, dealer_short, dealer_spread, dealer_net,
                        asset_mgr_long, asset_mgr_short, asset_mgr_spread, asset_mgr_net,
                        lev_money_long, lev_money_short, lev_money_spread, lev_money_net,
                        other_long, other_short, other_spread, other_net,
                        nonrept_long, nonrept_short, nonrept_net
                    ) VALUES (
                        :date, :asset_code, :asset_name, :oi,
                        :dealer_long, :dealer_short, :dealer_spread, :dealer_net,
                        :asset_mgr_long, :asset_mgr_short, :asset_mgr_spread, :asset_mgr_net,
                        :lev_money_long, :lev_money_short, :lev_money_spread, :lev_money_net,
                        :other_long, :other_short, :other_spread, :other_net,
                        :nonrept_long, :nonrept_short, :nonrept_net
                    )
                    ON CONFLICT (date, asset_code) DO UPDATE SET
                        dealer_long = EXCLUDED.dealer_long, dealer_short = EXCLUDED.dealer_short,
                        dealer_spread = EXCLUDED.dealer_spread, dealer_net = EXCLUDED.dealer_net,
                        asset_mgr_long = EXCLUDED.asset_mgr_long, asset_mgr_short = EXCLUDED.asset_mgr_short,
                        asset_mgr_spread = EXCLUDED.asset_mgr_spread, asset_mgr_net = EXCLUDED.asset_mgr_net,
                        lev_money_long = EXCLUDED.lev_money_long, lev_money_short = EXCLUDED.lev_money_short,
                        lev_money_spread = EXCLUDED.lev_money_spread, lev_money_net = EXCLUDED.lev_money_net,
                        other_long = EXCLUDED.other_long, other_short = EXCLUDED.other_short,
                        other_spread = EXCLUDED.other_spread, other_net = EXCLUDED.other_net,
                        nonrept_long = EXCLUDED.nonrept_long, nonrept_short = EXCLUDED.nonrept_short,
                        nonrept_net = EXCLUDED.nonrept_net,
                        updated_at = NOW()
                """), {
                    "date": date_str, "asset_code": asset_code, "asset_name": asset_name,
                    "oi": self._sf(row.get("Open_Interest_All")),
                    "dealer_long": dealer_long, "dealer_short": dealer_short,
                    "dealer_spread": dealer_spread, "dealer_net": dealer_net,
                    "asset_mgr_long": asset_mgr_long, "asset_mgr_short": asset_mgr_short,
                    "asset_mgr_spread": asset_mgr_spread, "asset_mgr_net": asset_mgr_net,
                    "lev_money_long": lev_money_long, "lev_money_short": lev_money_short,
                    "lev_money_spread": lev_money_spread, "lev_money_net": lev_money_net,
                    "other_long": other_long, "other_short": other_short,
                    "other_spread": other_spread, "other_net": other_net,
                    "nonrept_long": nonrept_long, "nonrept_short": nonrept_short,
                    "nonrept_net": nonrept_net,
                })
                count += 1

            session.commit()

        logger.info(f"[CftcPositioning] TFF updated: {count} new rows")
        return count

    def update_latest_legacy(self) -> int:
        """CFTC Legacy Futures Only APIから最新データを取得しDBに追記"""
        import requests
        from core.database import SessionLocal
        from sqlalchemy import text

        try:
            logger.info("[CftcPositioning] Downloading Legacy latest data ...")
            resp = requests.get(LEGACY_API_URL, timeout=600)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text), low_memory=False)
        except Exception as e:
            logger.error(f"[CftcPositioning] Legacy API error: {e}")
            return 0

        df["CFTC_Contract_Market_Code"] = df["CFTC_Contract_Market_Code"].astype(str).str.strip()

        with SessionLocal() as session:
            result = session.execute(text(
                "SELECT asset_code, MAX(date) FROM cftc_legacy_positions GROUP BY asset_code"
            ))
            db_latest = {row[0]: row[1] for row in result}

        df_filtered = df[df["CFTC_Contract_Market_Code"].isin(TFF_ASSETS.keys())]
        count = 0

        with SessionLocal() as session:
            for _, row in df_filtered.iterrows():
                asset_code = row["CFTC_Contract_Market_Code"]
                asset_name = TFF_ASSETS[asset_code]

                date_raw = row.get("Report_Date_as_YYYY_MM_DD")
                if pd.isna(date_raw):
                    continue
                try:
                    date_parsed = pd.to_datetime(date_raw)
                    date_str = date_parsed.strftime("%Y-%m-%d")
                    report_date = date_parsed.date()
                except Exception:
                    continue

                existing_max = db_latest.get(asset_code)
                if existing_max and report_date <= existing_max:
                    continue

                noncomm_long = self._sf(row.get("NonComm_Positions_Long_All"))
                noncomm_short = self._sf(row.get("NonComm_Positions_Short_All"))
                noncomm_spread = self._sf(row.get("NonComm_Postions_Spread_All",
                                          row.get("NonComm_Positions_Spread_All")))
                noncomm_net = (noncomm_long - noncomm_short) if noncomm_long is not None and noncomm_short is not None else None

                comm_long = self._sf(row.get("Comm_Positions_Long_All"))
                comm_short = self._sf(row.get("Comm_Positions_Short_All"))
                comm_net = (comm_long - comm_short) if comm_long is not None and comm_short is not None else None

                nonrept_long = self._sf(row.get("NonRept_Positions_Long_All"))
                nonrept_short = self._sf(row.get("NonRept_Positions_Short_All"))
                nonrept_net = (nonrept_long - nonrept_short) if nonrept_long is not None and nonrept_short is not None else None

                session.execute(text("""
                    INSERT INTO cftc_legacy_positions (
                        date, asset_code, asset_name, open_interest,
                        noncomm_long, noncomm_short, noncomm_spread, noncomm_net,
                        comm_long, comm_short, comm_net,
                        nonrept_long, nonrept_short, nonrept_net
                    ) VALUES (
                        :date, :asset_code, :asset_name, :oi,
                        :noncomm_long, :noncomm_short, :noncomm_spread, :noncomm_net,
                        :comm_long, :comm_short, :comm_net,
                        :nonrept_long, :nonrept_short, :nonrept_net
                    )
                    ON CONFLICT (date, asset_code) DO UPDATE SET
                        noncomm_long = EXCLUDED.noncomm_long, noncomm_short = EXCLUDED.noncomm_short,
                        noncomm_spread = EXCLUDED.noncomm_spread, noncomm_net = EXCLUDED.noncomm_net,
                        comm_long = EXCLUDED.comm_long, comm_short = EXCLUDED.comm_short,
                        comm_net = EXCLUDED.comm_net,
                        nonrept_long = EXCLUDED.nonrept_long, nonrept_short = EXCLUDED.nonrept_short,
                        nonrept_net = EXCLUDED.nonrept_net,
                        updated_at = NOW()
                """), {
                    "date": date_str, "asset_code": asset_code, "asset_name": asset_name,
                    "oi": self._sf(row.get("Open_Interest_All")),
                    "noncomm_long": noncomm_long, "noncomm_short": noncomm_short,
                    "noncomm_spread": noncomm_spread, "noncomm_net": noncomm_net,
                    "comm_long": comm_long, "comm_short": comm_short, "comm_net": comm_net,
                    "nonrept_long": nonrept_long, "nonrept_short": nonrept_short,
                    "nonrept_net": nonrept_net,
                })
                count += 1

            session.commit()

        logger.info(f"[CftcPositioning] Legacy updated: {count} new rows")
        return count

    def update_all_latest(self) -> Dict[str, int]:
        """DisAgg + TFF + Legacy の最新データを更新"""
        disagg_count = self.update_latest_disagg()
        tff_count = self.update_latest_tff()
        legacy_count = self.update_latest_legacy()

        # Clear all caches so next request rebuilds
        for asset in ALL_ASSETS:
            try:
                redis_client.delete(self._cache_key(asset))
            except Exception:
                pass

        return {"disagg": disagg_count, "tff": tff_count, "legacy": legacy_count}

    @staticmethod
    def _sf(val):
        """Safe float conversion."""
        if pd.isna(val) if not isinstance(val, str) else False:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _save_to_cache(self, asset: str, data: Dict[str, Any]) -> None:
        try:
            redis_client.set(self._cache_key(asset), data, expire=86400)
        except Exception as e:
            logger.warning(f"[CftcPositioning] Redis save error: {e}")

        try:
            with open(self._cache_file(asset), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"[CftcPositioning] File save error: {e}")

    def _load_from_redis(self, asset: str) -> Optional[Dict[str, Any]]:
        try:
            data = redis_client.get(self._cache_key(asset))
            if data:
                data["cached"] = True
                data["source"] = "redis"
                return data
        except Exception:
            pass
        return None

    def _load_from_file(self, asset: str) -> Optional[Dict[str, Any]]:
        try:
            cache_file = self._cache_file(asset)
            if cache_file.exists():
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["cached"] = True
                data["source"] = "file"
                return data
        except Exception:
            pass
        return None


cftc_positioning_service = CftcPositioningService()
