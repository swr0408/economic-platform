"""Earnings service.

Provides:
  - Per-country earnings calendar (next 60 days, filtered to target companies)
  - Per-country earnings data (historical EPS/revenue results + surprises)
  - Global calendar endpoint (all countries merged)
  - JSON file cache with configurable TTL
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from backend.services.earnings.providers.fmp_earnings_provider import fmp_earnings_provider
    from backend.services.earnings.ir_links import IR_LINKS
except ImportError:
    from services.earnings.providers.fmp_earnings_provider import fmp_earnings_provider
    from services.earnings.ir_links import IR_LINKS

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "earnings"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

UTC = timezone.utc

# Calendar window: today-7d to today+60d
CALENDAR_PAST_DAYS   = 7
CALENDAR_FUTURE_DAYS = 60
HISTORY_LIMIT        = 20  # historical earnings per symbol


# ---------------------------------------------------------------------------
# Target company definitions
# Tier: S / A / B
# ---------------------------------------------------------------------------
_COMPANIES: Dict[str, List[Dict[str, str]]] = {
    "usa": [
        # S
        {"ticker": "NVDA",  "name": "NVIDIA",              "tier": "S"},
        {"ticker": "AAPL",  "name": "Apple",               "tier": "S"},
        {"ticker": "MSFT",  "name": "Microsoft",           "tier": "S"},
        {"ticker": "AMZN",  "name": "Amazon",              "tier": "S"},
        {"ticker": "GOOGL", "name": "Alphabet",            "tier": "S"},
        {"ticker": "META",  "name": "Meta",                "tier": "S"},
        {"ticker": "AVGO",  "name": "Broadcom",            "tier": "S"},
        {"ticker": "TSLA",  "name": "Tesla",               "tier": "S"},
        {"ticker": "BRK-B", "name": "Berkshire Hathaway",  "tier": "S"},
        {"ticker": "JPM",   "name": "JPMorgan Chase",      "tier": "S"},
        # A
        {"ticker": "V",     "name": "Visa",                "tier": "A"},
        {"ticker": "MA",    "name": "Mastercard",          "tier": "A"},
        {"ticker": "LLY",   "name": "Eli Lilly",           "tier": "A"},
        {"ticker": "XOM",   "name": "Exxon Mobil",         "tier": "A"},
        {"ticker": "CVX",   "name": "Chevron",             "tier": "A"},
        {"ticker": "BAC",   "name": "Bank of America",     "tier": "A"},
        {"ticker": "GS",    "name": "Goldman Sachs",       "tier": "A"},
        {"ticker": "WFC",   "name": "Wells Fargo",         "tier": "A"},
        {"ticker": "MS",    "name": "Morgan Stanley",      "tier": "A"},
        {"ticker": "NFLX",  "name": "Netflix",             "tier": "A"},
        # B
        {"ticker": "UNH",   "name": "UnitedHealth",        "tier": "B"},
        {"ticker": "JNJ",   "name": "Johnson & Johnson",   "tier": "B"},
        {"ticker": "ABBV",  "name": "AbbVie",              "tier": "B"},
        {"ticker": "MRK",   "name": "Merck",               "tier": "B"},
        {"ticker": "CAT",   "name": "Caterpillar",         "tier": "B"},
        {"ticker": "GE",    "name": "GE Aerospace",        "tier": "B"},
        {"ticker": "RTX",   "name": "RTX",                 "tier": "B"},
    ],
    "japan": [
        # S
        {"ticker": "6857.T",  "name": "Advantest",          "tier": "S"},
        {"ticker": "9983.T",  "name": "Fast Retailing",     "tier": "S"},
        {"ticker": "8035.T",  "name": "Tokyo Electron",     "tier": "S"},
        {"ticker": "9984.T",  "name": "SoftBank Group",     "tier": "S"},
        {"ticker": "7203.T",  "name": "Toyota",             "tier": "S"},
        {"ticker": "8306.T",  "name": "Mitsubishi UFJ",     "tier": "S"},
        # A
        {"ticker": "6501.T",  "name": "Hitachi",            "tier": "A"},
        {"ticker": "6758.T",  "name": "Sony",               "tier": "A"},
        {"ticker": "8316.T",  "name": "SMFG",               "tier": "A"},
        {"ticker": "8411.T",  "name": "Mizuho",             "tier": "A"},
        {"ticker": "8058.T",  "name": "Mitsubishi Corp",    "tier": "A"},
        {"ticker": "7011.T",  "name": "Mitsubishi Heavy",   "tier": "A"},
        {"ticker": "4063.T",  "name": "Shin-Etsu Chemical", "tier": "A"},
        {"ticker": "9433.T",  "name": "KDDI",               "tier": "A"},
        {"ticker": "6762.T",  "name": "TDK",                "tier": "A"},
        {"ticker": "6954.T",  "name": "FANUC",              "tier": "A"},
        {"ticker": "4519.T",  "name": "Chugai",             "tier": "A"},
        # B
        {"ticker": "5803.T",  "name": "Fujikura",           "tier": "B"},
    ],
    "netherlands": [
        {"ticker": "ASML",   "name": "ASML",               "tier": "S"},
        {"ticker": "ING",    "name": "ING",                "tier": "A"},
        {"ticker": "PRX",    "name": "Prosus",             "tier": "A"},
        {"ticker": "ASM",    "name": "ASM International",  "tier": "A"},
        {"ticker": "ADYEN",  "name": "Adyen",              "tier": "A"},
        {"ticker": "AD",     "name": "Ahold Delhaize",     "tier": "A"},
    ],
    "uk": [
        {"ticker": "AZN",    "name": "AstraZeneca",        "tier": "S"},
        {"ticker": "HSBA",   "name": "HSBC",               "tier": "S"},
        {"ticker": "SHEL",   "name": "Shell",              "tier": "S"},
        {"ticker": "ULVR",   "name": "Unilever",           "tier": "A"},
        {"ticker": "RR",     "name": "Rolls-Royce",        "tier": "A"},
        {"ticker": "GSK",    "name": "GSK",                "tier": "A"},
        {"ticker": "RIO",    "name": "Rio Tinto",          "tier": "A"},
        {"ticker": "BP",     "name": "BP",                 "tier": "A"},
        {"ticker": "NG",     "name": "National Grid",      "tier": "A"},
    ],
    "switzerland": [
        {"ticker": "ROG",    "name": "Roche",              "tier": "S"},
        {"ticker": "NOVN",   "name": "Novartis",           "tier": "S"},
        {"ticker": "NESN",   "name": "Nestlé",             "tier": "S"},
        {"ticker": "UBSG",   "name": "UBS",                "tier": "A"},
        {"ticker": "ABBN",   "name": "ABB",                "tier": "A"},
        {"ticker": "ZURN",   "name": "Zurich Insurance",   "tier": "A"},
        {"ticker": "CFR",    "name": "Richemont",          "tier": "A"},
    ],
    "germany": [
        {"ticker": "SIE",    "name": "Siemens",            "tier": "S"},
        {"ticker": "SAP",    "name": "SAP",                "tier": "S"},
        {"ticker": "ALV",    "name": "Allianz",            "tier": "A"},
        {"ticker": "ENR",    "name": "Siemens Energy",     "tier": "A"},
        {"ticker": "DTE",    "name": "Deutsche Telekom",   "tier": "A"},
        {"ticker": "IFX",    "name": "Infineon",           "tier": "A"},
        {"ticker": "DBK",    "name": "Deutsche Bank",      "tier": "A"},
        {"ticker": "MUV2",   "name": "Munich Re",          "tier": "A"},
        {"ticker": "RHM",    "name": "Rheinmetall",        "tier": "A"},
    ],
    "denmark": [
        {"ticker": "NOVO-B",   "name": "Novo Nordisk",      "tier": "S"},
        {"ticker": "DSV",      "name": "DSV",               "tier": "A"},
        {"ticker": "DANSKE",   "name": "Danske Bank",       "tier": "A"},
        {"ticker": "VWS",      "name": "Vestas",            "tier": "A"},
        {"ticker": "NZYM-B",   "name": "Novonesis",         "tier": "A"},
        {"ticker": "GMAB",     "name": "Genmab",            "tier": "A"},
        {"ticker": "MAERSK-B", "name": "AP Moller Maersk",  "tier": "A"},
    ],
    "france": [
        {"ticker": "SU",     "name": "Schneider Electric", "tier": "A"},
        {"ticker": "MC",     "name": "LVMH",               "tier": "A"},
        {"ticker": "TTE",    "name": "TotalEnergies",      "tier": "A"},
        {"ticker": "SAF",    "name": "Safran",             "tier": "A"},
        {"ticker": "AIR",    "name": "Airbus",             "tier": "A"},
        {"ticker": "SAN",    "name": "Sanofi",             "tier": "A"},
        {"ticker": "BNP",    "name": "BNP Paribas",        "tier": "A"},
        {"ticker": "CS",     "name": "AXA",                "tier": "A"},
    ],
    "taiwan": [
        {"ticker": "TSM",      "name": "TSMC",              "tier": "S"},
        {"ticker": "2317.TW",  "name": "Hon Hai",           "tier": "A"},
        {"ticker": "2454.TW",  "name": "MediaTek",          "tier": "A"},
    ],
    "southkorea": [
        {"ticker": "005930.KS", "name": "Samsung Electronics", "tier": "S"},
        {"ticker": "000660.KS", "name": "SK hynix",            "tier": "S"},
        {"ticker": "005380.KS", "name": "Hyundai Motor",       "tier": "A"},
        {"ticker": "105560.KS", "name": "KB Financial",        "tier": "A"},
        {"ticker": "000270.KS", "name": "Kia",                 "tier": "A"},
        {"ticker": "055550.KS", "name": "Shinhan Financial",   "tier": "A"},
        {"ticker": "012450.KS", "name": "Hanwha Aerospace",    "tier": "A"},
        {"ticker": "034020.KS", "name": "Doosan Enerbility",   "tier": "A"},
    ],
    "china-hongkong": [
        {"ticker": "0700.HK",  "name": "Tencent",                "tier": "S"},
        {"ticker": "BABA",     "name": "Alibaba",                "tier": "S"},
        {"ticker": "1810.HK",  "name": "Xiaomi",                 "tier": "A"},
        {"ticker": "PDD",      "name": "PDD",                    "tier": "A"},
        {"ticker": "3690.HK",  "name": "Meituan",                "tier": "A"},
        {"ticker": "1211.HK",  "name": "BYD",                    "tier": "A"},
        {"ticker": "0939.HK",  "name": "China Construction Bank","tier": "B"},
        {"ticker": "2318.HK",  "name": "Ping An",                "tier": "B"},
        {"ticker": "1398.HK",  "name": "ICBC",                   "tier": "B"},
        {"ticker": "3988.HK",  "name": "Bank of China",          "tier": "B"},
    ],
    "india": [
        {"ticker": "HDFCBANK.NS",  "name": "HDFC Bank",            "tier": "S"},
        {"ticker": "RELIANCE.NS",  "name": "Reliance Industries",  "tier": "S"},
        {"ticker": "ICICIBANK.NS", "name": "ICICI Bank",           "tier": "S"},
        {"ticker": "BHARTIARTL.NS","name": "Bharti Airtel",        "tier": "A"},
        {"ticker": "INFY.NS",      "name": "Infosys",              "tier": "A"},
        {"ticker": "AXISBANK.NS",  "name": "Axis Bank",            "tier": "A"},
        {"ticker": "LT.NS",        "name": "Larsen & Toubro",      "tier": "A"},
        {"ticker": "M&M.NS",       "name": "Mahindra & Mahindra",  "tier": "A"},
        {"ticker": "TCS.NS",       "name": "Tata Consultancy",     "tier": "A"},
        {"ticker": "BAJFINANCE.NS","name": "Bajaj Finance",        "tier": "A"},
    ],
    "canada": [
        {"ticker": "RY",     "name": "Royal Bank of Canada",       "tier": "A"},
        {"ticker": "TD",     "name": "TD",                         "tier": "A"},
        {"ticker": "SHOP",   "name": "Shopify",                    "tier": "A"},
        {"ticker": "AEM",    "name": "Agnico Eagle",               "tier": "A"},
        {"ticker": "ENB",    "name": "Enbridge",                   "tier": "A"},
        {"ticker": "CNQ",    "name": "Canadian Natural Resources", "tier": "A"},
        {"ticker": "BAM",    "name": "Brookfield",                 "tier": "A"},
    ],
    "australia": [
        {"ticker": "BHP.AX",  "name": "BHP",                "tier": "A"},
        {"ticker": "CBA.AX",  "name": "Commonwealth Bank",  "tier": "A"},
        {"ticker": "NAB.AX",  "name": "NAB",                "tier": "A"},
        {"ticker": "WBC.AX",  "name": "Westpac",            "tier": "A"},
        {"ticker": "ANZ.AX",  "name": "ANZ",                "tier": "A"},
        {"ticker": "MQG.AX",  "name": "Macquarie",          "tier": "A"},
        {"ticker": "CSL.AX",  "name": "CSL",                "tier": "A"},
        {"ticker": "RIO.AX",  "name": "Rio Tinto Ltd",      "tier": "A"},
    ],
}

# Pre-build per-country company maps: {ticker_upper: {name, tier, country_code}}
def _build_company_map(country_code: str) -> Dict[str, Dict[str, str]]:
    return {
        c["ticker"].upper(): {
            "name": c["name"],
            "tier": c["tier"],
            "country_code": country_code,
        }
        for c in _COMPANIES.get(country_code, [])
    }

# Global map across all countries
_GLOBAL_COMPANY_MAP: Dict[str, Dict[str, str]] = {}
for _cc, _comps in _COMPANIES.items():
    for _c in _comps:
        _GLOBAL_COMPANY_MAP[_c["ticker"].upper()] = {
            "name": _c["name"],
            "tier": _c["tier"],
            "country_code": _cc,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

SUPPORTED_COUNTRIES: List[Dict[str, Any]] = [
    {"code": "usa",           "name": "United States",     "provider_countries": ["US"]},
    {"code": "japan",         "name": "Japan",             "provider_countries": ["JP"]},
    {"code": "netherlands",   "name": "Netherlands",       "provider_countries": ["NL"]},
    {"code": "uk",            "name": "United Kingdom",    "provider_countries": ["GB"]},
    {"code": "switzerland",   "name": "Switzerland",       "provider_countries": ["CH"]},
    {"code": "germany",       "name": "Germany",           "provider_countries": ["DE"]},
    {"code": "denmark",       "name": "Denmark",           "provider_countries": ["DK"]},
    {"code": "france",        "name": "France",            "provider_countries": ["FR"]},
    {"code": "taiwan",        "name": "Taiwan",            "provider_countries": ["TW"]},
    {"code": "southkorea",    "name": "South Korea",       "provider_countries": ["KR"]},
    {"code": "china-hongkong","name": "China / Hong Kong", "provider_countries": ["CN", "HK"]},
    {"code": "india",         "name": "India",             "provider_countries": ["IN"]},
    {"code": "canada",        "name": "Canada",            "provider_countries": ["CA"]},
    {"code": "australia",     "name": "Australia",         "provider_countries": ["AU"]},
]

CALENDAR_TTL_HOURS   = 6
DATA_TTL_HOURS       = 24
FINANCIALS_TTL_HOURS = 24
FINANCIALS_QUARTERS  = 8   # 8 quarters (2 years)

# ---------------------------------------------------------------------------
# Sector classification per ticker (upper-case)
# 'bank' | 'tech' | 'energy' | 'default'
# ---------------------------------------------------------------------------
_SECTORS: Dict[str, str] = {
    # Banks / Insurance
    "JPM": "bank", "BAC": "bank", "GS": "bank", "WFC": "bank", "MS": "bank",
    "8306.T": "bank", "8316.T": "bank", "8411.T": "bank",
    "ING": "bank", "HSBA": "bank", "UBSG": "bank", "DBK": "bank",
    "DANSKE": "bank", "BNP": "bank", "CS": "bank",
    "0939.HK": "bank", "2318.HK": "bank", "1398.HK": "bank", "3988.HK": "bank",
    "105560.KS": "bank", "055550.KS": "bank",
    "HDFCBANK.NS": "bank", "ICICIBANK.NS": "bank", "AXISBANK.NS": "bank",
    "BAJFINANCE.NS": "bank",
    "RY": "bank", "TD": "bank",
    "CBA.AX": "bank", "NAB.AX": "bank", "WBC.AX": "bank", "ANZ.AX": "bank",
    "MQG.AX": "bank",
    # Insurance
    "BRK-B": "bank", "ALV": "bank", "MUV2": "bank", "ZURN": "bank",
    # Tech / Semiconductors
    "NVDA": "tech", "AAPL": "tech", "MSFT": "tech", "AMZN": "tech",
    "GOOGL": "tech", "META": "tech", "AVGO": "tech", "NFLX": "tech",
    "TSM": "tech", "ASML": "tech", "ASM": "tech",
    "6857.T": "tech", "8035.T": "tech",
    "005930.KS": "tech", "000660.KS": "tech",
    "2317.TW": "tech", "2454.TW": "tech",
    "0700.HK": "tech", "BABA": "tech", "1810.HK": "tech",
    "PDD": "tech", "3690.HK": "tech",
    "INFY.NS": "tech", "TCS.NS": "tech",
    "SHOP": "tech", "ADYEN": "tech",
    "SAP": "tech", "IFX": "tech",
    # Energy / Resources / Heavy Industry
    "XOM": "energy", "CVX": "energy",
    "SHEL": "energy", "BP": "energy", "TTE": "energy",
    "RIO": "energy", "RIO.AX": "energy", "BHP.AX": "energy",
    "ENB": "energy", "CNQ": "energy",
    "RELIANCE.NS": "energy",
    "1211.HK": "energy",
    "7011.T": "energy", "8058.T": "energy",
    "RHM": "energy", "ENR": "energy",
    "034020.KS": "energy", "012450.KS": "energy",
}

_COUNTRY_MAP: Dict[str, Dict[str, Any]] = {c["code"]: c for c in SUPPORTED_COUNTRIES}


class EarningsService:

    # ------------------------------------------------------------------
    # Public: countries
    # ------------------------------------------------------------------

    def list_countries(self) -> Dict[str, Any]:
        return {
            "countries": [
                {
                    **country,
                    "company_count": len(_COMPANIES.get(country["code"], [])),
                    "last_updated": self._country_last_updated(country["code"]),
                }
                for country in SUPPORTED_COUNTRIES
            ],
            "total": len(SUPPORTED_COUNTRIES),
        }

    # ------------------------------------------------------------------
    # Public: calendar
    # ------------------------------------------------------------------

    def get_calendar(self, country_code: str) -> Dict[str, Any]:
        country = self._require_country(country_code)

        # Try cache first
        cached = self._read_cache(country_code, "calendar")
        if cached is not None and not self._is_stale(country_code, "calendar", CALENDAR_TTL_HOURS):
            cached["cached"] = True
            return cached

        # Fetch fresh data
        try:
            payload = self._fetch_calendar(country_code, country)
            self._write_cache(country_code, "calendar", payload)
            return payload
        except Exception as exc:
            logger.error("Error fetching calendar for %s: %s", country_code, exc)
            if cached is not None:
                cached["cached"] = True
                cached["stale"] = True
                return cached
            return self._empty_calendar(country_code, country)

    def get_calendar_all(self) -> Dict[str, Any]:
        """Return merged calendar for all countries (date=None entries included)."""
        all_items: List[Dict[str, Any]] = []
        now = datetime.now(tz=UTC)

        for country in SUPPORTED_COUNTRIES:
            try:
                cal = self.get_calendar(country["code"])
                all_items.extend(cal.get("items", []))
            except Exception as exc:
                logger.warning("get_calendar_all skip %s: %s", country["code"], exc)

        # 日付あり → 昇順, 日付なし → 末尾
        all_items.sort(key=lambda x: (x.get("date") is None, x.get("date") or ""))

        today = date.today()
        today_str = today.isoformat()
        d7  = (today + timedelta(days=7)).isoformat()
        d30 = (today + timedelta(days=30)).isoformat()

        return {
            "country": "all",
            "country_name": "Global",
            "items": all_items,
            "next_7d_count":  sum(1 for i in all_items if i.get("date") and today_str <= i["date"] <= d7),
            "next_30d_count": sum(1 for i in all_items if i.get("date") and today_str <= i["date"] <= d30),
            "last_updated": now.isoformat(),
            "cached": False,
            "status": "ok",
        }

    # ------------------------------------------------------------------
    # Public: data (historical earnings)
    # ------------------------------------------------------------------

    def get_data(self, country_code: str) -> Dict[str, Any]:
        country = self._require_country(country_code)

        cached = self._read_cache(country_code, "data")
        if cached is not None and not self._is_stale(country_code, "data", DATA_TTL_HOURS):
            cached["cached"] = True
            return cached

        try:
            payload = self._fetch_data(country_code, country)
            self._write_cache(country_code, "data", payload)
            return payload
        except Exception as exc:
            logger.error("Error fetching data for %s: %s", country_code, exc)
            if cached is not None:
                cached["cached"] = True
                cached["stale"] = True
                return cached
            return self._empty_data(country_code, country)

    # ------------------------------------------------------------------
    # Public: financials (IS / CF / BS merged, per symbol)
    # ------------------------------------------------------------------

    def get_financials(self, country_code: str, ticker: str) -> Dict[str, Any]:
        """Return merged quarterly financials for a single ticker."""
        country = self._require_country(country_code)
        ticker_upper = ticker.upper()

        # Validate ticker belongs to this country
        companies = _COMPANIES.get(country_code, [])
        comp = next((c for c in companies if c["ticker"].upper() == ticker_upper), None)
        if comp is None:
            raise ValueError(f"Ticker {ticker} not in country {country_code}")

        cached = self._read_cache(country_code, f"financials_{ticker_upper}")
        if cached is not None and not self._is_stale(country_code, f"financials_{ticker_upper}", FINANCIALS_TTL_HOURS):
            cached["cached"] = True
            return cached

        try:
            payload = self._fetch_financials(ticker_upper, comp, country_code, country)
            self._write_cache(country_code, f"financials_{ticker_upper}", payload)
            return payload
        except Exception as exc:
            logger.error("Error fetching financials for %s/%s: %s", country_code, ticker, exc)
            if cached is not None:
                cached["cached"] = True
                cached["stale"] = True
                return cached
            return self._empty_financials(ticker_upper, comp, country_code, country)

    def _fetch_financials(
        self,
        ticker_upper: str,
        comp: Dict[str, str],
        country_code: str,
        country: Dict[str, Any],
    ) -> Dict[str, Any]:
        sector = _SECTORS.get(ticker_upper, "default")
        limit  = FINANCIALS_QUARTERS

        is_list = fmp_earnings_provider.fetch_income_statement(ticker_upper, limit=limit)
        cf_list = fmp_earnings_provider.fetch_cash_flow_statement(ticker_upper, limit=limit)
        bs_list = fmp_earnings_provider.fetch_balance_sheet_statement(ticker_upper, limit=limit)

        periods = fmp_earnings_provider.normalise_financials(is_list, cf_list, bs_list, sector)

        # Compute YoY growth (revenue, EPS) vs same quarter last year
        _add_yoy(periods)

        ir = IR_LINKS.get(ticker_upper, {})

        return {
            "ticker":        ticker_upper,
            "name":          comp["name"],
            "tier":          comp["tier"],
            "sector":        sector,
            "country_code":  country_code,
            "country_name":  country["name"],
            "reported_currency": periods[0]["reported_currency"] if periods else "",
            "periods":       periods,
            "ir_home":       ir.get("home", ""),
            "ir_results":    ir.get("results", ""),
            "ir_tdnet":      ir.get("tdnet", ""),
            "ir_notes":      ir.get("notes", ""),
            "last_updated":  datetime.now(tz=UTC).isoformat(),
            "cached":        False,
            "status":        "ok",
        }

    def _empty_financials(
        self,
        ticker_upper: str,
        comp: Dict[str, str],
        country_code: str,
        country: Dict[str, Any],
    ) -> Dict[str, Any]:
        ir = IR_LINKS.get(ticker_upper, {})
        return {
            "ticker":        ticker_upper,
            "name":          comp["name"],
            "tier":          comp["tier"],
            "sector":        _SECTORS.get(ticker_upper, "default"),
            "country_code":  country_code,
            "country_name":  country["name"],
            "reported_currency": "",
            "periods":       [],
            "ir_home":       ir.get("home", ""),
            "ir_results":    ir.get("results", ""),
            "ir_tdnet":      ir.get("tdnet", ""),
            "ir_notes":      ir.get("notes", ""),
            "last_updated":  None,
            "cached":        False,
            "status":        "error",
        }

    # ------------------------------------------------------------------
    # Public: status / invalidate
    # ------------------------------------------------------------------

    def get_status(self, country_code: str) -> Dict[str, Any]:
        country = self._require_country(country_code)
        return {
            "country": country_code,
            "country_name": country["name"],
            "provider_countries": country["provider_countries"],
            "calendar": self._cache_metadata(country_code, "calendar", CALENDAR_TTL_HOURS),
            "data":     self._cache_metadata(country_code, "data",     DATA_TTL_HOURS),
        }

    def invalidate_cache(self, country_code: str) -> Dict[str, Any]:
        self._require_country(country_code)
        deleted: List[str] = []
        # calendar + data + all financials_<TICKER> files for this country
        for p in CACHE_DIR.glob(f"earnings_{country_code}_*.json"):
            p.unlink()
            deleted.append(p.name)
        return {"country": country_code, "success": True, "deleted_files": deleted}

    # ------------------------------------------------------------------
    # Private: fetch calendar
    # ------------------------------------------------------------------

    def _fetch_calendar(self, country_code: str, country: Dict[str, Any]) -> Dict[str, Any]:
        company_map = _build_company_map(country_code)
        today = date.today()
        from_date = today - timedelta(days=CALENDAR_PAST_DAYS)
        to_date   = today + timedelta(days=CALENDAR_FUTURE_DAYS)

        raw_entries = fmp_earnings_provider.fetch_calendar_by_date(from_date, to_date)

        # FMP データから対象企業のエントリを収集（ticker → entry）
        fmp_map: Dict[str, Dict[str, Any]] = {}
        for raw in raw_entries:
            entry = fmp_earnings_provider.normalise_calendar_entry(raw, company_map)
            if entry is not None:
                ticker = entry["symbol"]
                # 同一ティッカーが複数ある場合は最も直近の日付を優先
                if ticker not in fmp_map or entry.get("date", "") > fmp_map[ticker].get("date", ""):
                    fmp_map[ticker] = entry

        # 対象全企業を必ず含める。FMPにないものは date=None で補完
        items: List[Dict[str, Any]] = []
        for comp in _COMPANIES.get(country_code, []):
            ticker_upper = comp["ticker"].upper()
            if ticker_upper in fmp_map:
                items.append(fmp_map[ticker_upper])
            else:
                items.append({
                    "symbol":            comp["ticker"],
                    "name":              comp["name"],
                    "tier":              comp["tier"],
                    "country_code":      country_code,
                    "date":              None,
                    "time":              None,
                    "fiscal_date_ending": None,
                    "eps_estimate":      None,
                    "eps_actual":        None,
                    "revenue_estimate":  None,
                    "revenue_actual":    None,
                    "updated_from_date": None,
                })

        # 日付あり → 昇順, 日付なし → 末尾
        items.sort(key=lambda x: (x.get("date") is None, x.get("date") or ""))

        today_str = today.isoformat()
        d7  = (today + timedelta(days=7)).isoformat()
        d30 = (today + timedelta(days=30)).isoformat()

        payload = {
            "country": country_code,
            "country_name": country["name"],
            "provider_countries": country["provider_countries"],
            "items": items,
            "next_7d_count":  sum(1 for i in items if i.get("date") and today_str <= i["date"] <= d7),
            "next_30d_count": sum(1 for i in items if i.get("date") and today_str <= i["date"] <= d30),
            "last_updated": datetime.now(tz=UTC).isoformat(),
            "cached": False,
            "status": "ok",
        }
        return payload

    # ------------------------------------------------------------------
    # Private: fetch historical data
    # ------------------------------------------------------------------

    def _fetch_data(self, country_code: str, country: Dict[str, Any]) -> Dict[str, Any]:
        companies = _COMPANIES.get(country_code, [])
        all_results: List[Dict[str, Any]] = []

        for comp in companies:
            try:
                raw_list = fmp_earnings_provider.fetch_historical_earnings(
                    comp["ticker"], limit=HISTORY_LIMIT
                )
                for raw in raw_list:
                    entry = fmp_earnings_provider.normalise_historical_entry(raw, comp)
                    all_results.append(entry)
            except Exception as exc:
                logger.warning("fetch_data skip %s: %s", comp["ticker"], exc)

        # Sort by date desc
        all_results.sort(key=lambda x: x.get("date", ""), reverse=True)

        # Latest results: most recent entry per symbol
        seen: set = set()
        latest: List[Dict[str, Any]] = []
        for r in all_results:
            sym = r["symbol"]
            if sym not in seen:
                seen.add(sym)
                latest.append(r)

        # Top EPS surprises (beat, descending)
        eps_surprises = sorted(
            [r for r in latest if r.get("eps_surprise_pct") is not None],
            key=lambda x: x["eps_surprise_pct"],
            reverse=True,
        )[:10]

        # Top revenue surprises (beat, descending)
        rev_surprises = sorted(
            [r for r in latest if r.get("revenue_surprise_pct") is not None],
            key=lambda x: x["revenue_surprise_pct"],
            reverse=True,
        )[:10]

        payload = {
            "country": country_code,
            "country_name": country["name"],
            "provider_countries": country["provider_countries"],
            "latest_results": latest,
            "top_eps_surprises": eps_surprises,
            "top_revenue_surprises": rev_surprises,
            "last_updated": datetime.now(tz=UTC).isoformat(),
            "cached": False,
            "status": "ok",
        }
        return payload

    # ------------------------------------------------------------------
    # Empty fallbacks
    # ------------------------------------------------------------------

    def _empty_calendar(self, country_code: str, country: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "country": country_code,
            "country_name": country["name"],
            "provider_countries": country["provider_countries"],
            "items": [],
            "next_7d_count": 0,
            "next_30d_count": 0,
            "last_updated": None,
            "cached": False,
            "status": "error",
        }

    def _empty_data(self, country_code: str, country: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "country": country_code,
            "country_name": country["name"],
            "provider_countries": country["provider_countries"],
            "latest_results": [],
            "top_eps_surprises": [],
            "top_revenue_surprises": [],
            "last_updated": None,
            "cached": False,
            "status": "error",
        }

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _require_country(self, country_code: str) -> Dict[str, Any]:
        country = _COUNTRY_MAP.get(country_code)
        if not country:
            raise ValueError(f"Unsupported earnings country: {country_code}")
        return country

    def _cache_path(self, country_code: str, category: str) -> Path:
        return CACHE_DIR / f"earnings_{country_code}_{category}_cache.json"

    def _read_cache(self, country_code: str, category: str) -> Optional[Dict[str, Any]]:
        p = self._cache_path(country_code, category)
        if not p.exists():
            return None
        try:
            with p.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return None

    def _write_cache(self, country_code: str, category: str, payload: Dict[str, Any]) -> None:
        p = self._cache_path(country_code, category)
        try:
            with p.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error("Failed to write cache %s: %s", p, exc)

    def _is_stale(self, country_code: str, category: str, ttl_hours: int) -> bool:
        p = self._cache_path(country_code, category)
        if not p.exists():
            return True
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
        return datetime.now(tz=UTC) > mtime + timedelta(hours=ttl_hours)

    def _country_last_updated(self, country_code: str) -> Optional[str]:
        timestamps = []
        for category in ("calendar", "data"):
            p = self._cache_path(country_code, category)
            if p.exists():
                timestamps.append(datetime.fromtimestamp(p.stat().st_mtime, tz=UTC))
        if not timestamps:
            return None
        return max(timestamps).isoformat()

    def _cache_metadata(self, country_code: str, category: str, ttl_hours: int) -> Dict[str, Any]:
        p = self._cache_path(country_code, category)
        if not p.exists():
            return {"exists": False, "cache_file": p.name, "last_updated": None,
                    "expires_at": None, "is_stale": True}
        updated_at  = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
        expires_at  = updated_at + timedelta(hours=ttl_hours)
        return {
            "exists": True,
            "cache_file": p.name,
            "last_updated": updated_at.isoformat(),
            "expires_at":   expires_at.isoformat(),
            "is_stale": datetime.now(tz=UTC) > expires_at,
        }


def _add_yoy(periods: List[Dict[str, Any]]) -> None:
    """Add revenue_yoy and eps_yoy (%) by comparing period N to period N+4 (same quarter last year)."""
    for i, rec in enumerate(periods):
        yoy_idx = i + 4
        if yoy_idx < len(periods):
            prev = periods[yoy_idx]
            rev_cur  = rec.get("revenue")
            rev_prev = prev.get("revenue")
            if rev_cur is not None and rev_prev and rev_prev != 0:
                rec["revenue_yoy"] = (rev_cur - rev_prev) / abs(rev_prev) * 100
            else:
                rec["revenue_yoy"] = None

            eps_cur  = rec.get("eps_diluted")
            eps_prev = prev.get("eps_diluted")
            if eps_cur is not None and eps_prev and eps_prev != 0:
                rec["eps_yoy"] = (eps_cur - eps_prev) / abs(eps_prev) * 100
            else:
                rec["eps_yoy"] = None
        else:
            rec["revenue_yoy"] = None
            rec["eps_yoy"]     = None


earnings_service = EarningsService()
