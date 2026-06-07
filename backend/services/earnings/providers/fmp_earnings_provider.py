"""FMP earnings data provider.

Uses two FMP stable endpoints:
  - /stable/earnings-calendar  : upcoming / recent earnings by date range
  - /stable/earnings           : historical earnings per symbol (EPS actual/estimate)
"""

from __future__ import annotations

import os
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

FMP_API_KEY: str = os.getenv("FMP_API_KEY", "")
FMP_BASE_URL = "https://financialmodelingprep.com/stable"
FMP_TIMEOUT = 30

UTC = timezone.utc


class FMPEarningsProvider:
    """Fetch earnings calendar and historical earnings from FMP."""

    def __init__(self, api_key: str = FMP_API_KEY) -> None:
        self.api_key = api_key
        self._client: Optional[httpx.Client] = None

    @property
    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=FMP_TIMEOUT)
        return self._client

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_calendar_by_date(
        self,
        from_date: date,
        to_date: date,
    ) -> List[Dict[str, Any]]:
        """Fetch earnings calendar for a date range (all symbols).

        FMP endpoint: GET /stable/earnings-calendar
          params: from, to, apikey
        Returns list of dicts with keys: symbol, date, eps, epsEstimated,
          revenue, revenueEstimated, time, updatedFromDate, fiscalDateEnding
        """
        if not self.api_key:
            raise ValueError("FMP_API_KEY is not set")

        params = {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "apikey": self.api_key,
        }
        url = f"{FMP_BASE_URL}/earnings-calendar"
        try:
            resp = self._http.get(url, params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("FMP earnings-calendar HTTP error: %s", exc)
            raise

        data = resp.json()
        if isinstance(data, dict) and "error" in data:
            raise ValueError(f"FMP API error: {data['error']}")

        return data if isinstance(data, list) else []

    # ------------------------------------------------------------------
    # Financial statements (Income Statement / Cash Flow / Balance Sheet)
    # ------------------------------------------------------------------

    def fetch_income_statement(
        self,
        symbol: str,
        period: str = "quarter",
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        """GET /stable/income-statement  period=quarter|annual  limit=N."""
        return self._fetch_statement("income-statement", symbol, period, limit)

    def fetch_cash_flow_statement(
        self,
        symbol: str,
        period: str = "quarter",
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        """GET /stable/cash-flow-statement  period=quarter|annual  limit=N."""
        return self._fetch_statement("cash-flow-statement", symbol, period, limit)

    def fetch_balance_sheet_statement(
        self,
        symbol: str,
        period: str = "quarter",
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        """GET /stable/balance-sheet-statement  period=quarter|annual  limit=N."""
        return self._fetch_statement("balance-sheet-statement", symbol, period, limit)

    def _fetch_statement(
        self,
        endpoint: str,
        symbol: str,
        period: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        if not self.api_key:
            raise ValueError("FMP_API_KEY is not set")
        params = {
            "symbol": symbol,
            "period": period,
            "limit":  limit,
            "apikey": self.api_key,
        }
        url = f"{FMP_BASE_URL}/{endpoint}"
        try:
            resp = self._http.get(url, params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("FMP %s HTTP error for %s: %s", endpoint, symbol, exc)
            return []

        # FMP returns a JSON string ("Premium Query Parameter: ...") on tier
        # restriction. resp.json() decodes it to a Python str — handle that.
        try:
            data = resp.json()
        except ValueError:
            logger.warning("FMP %s non-JSON response for %s: %s",
                           endpoint, symbol, resp.text[:200])
            return []

        if isinstance(data, str):
            if "Premium" in data or "subscription" in data.lower():
                logger.warning(
                    "FMP %s requires premium subscription for %s: %s",
                    endpoint, symbol, data[:200],
                )
            else:
                logger.warning("FMP %s string response for %s: %s",
                               endpoint, symbol, data[:200])
            return []

        if isinstance(data, dict):
            msg = data.get("Error Message") or data.get("error") or data.get("message")
            if msg:
                logger.warning("FMP %s error for %s: %s", endpoint, symbol, msg)
                return []

        return data if isinstance(data, list) else []

    @staticmethod
    def normalise_financials(
        is_list: List[Dict[str, Any]],
        cf_list: List[Dict[str, Any]],
        bs_list: List[Dict[str, Any]],
        sector: str,
    ) -> List[Dict[str, Any]]:
        """Merge IS / CF / BS into per-period financial records.

        sector: 'default' | 'bank' | 'tech' | 'energy'
        """
        def _key(d: Dict[str, Any]) -> str:
            return f"{d.get('date', '')}__{d.get('period', '')}"

        cf_map = {_key(r): r for r in cf_list}
        bs_map = {_key(r): r for r in bs_list}

        results: List[Dict[str, Any]] = []
        for is_row in is_list:
            k = _key(is_row)
            cf = cf_map.get(k, {})
            bs = bs_map.get(k, {})

            revenue    = _to_float(is_row.get("revenue"))
            gross      = _to_float(is_row.get("grossProfit"))
            op_income  = _to_float(is_row.get("operatingIncome"))
            net_income = _to_float(is_row.get("netIncome"))
            op_cf      = _to_float(cf.get("operatingCashFlow"))
            fcf        = _to_float(cf.get("freeCashFlow"))
            capex      = _to_float(cf.get("capitalExpenditure"))
            buyback    = _to_float(cf.get("commonStockRepurchased"))
            dividends  = _to_float(cf.get("commonDividendsPaid") or cf.get("netDividendsPaid"))

            rec: Dict[str, Any] = {
                "date":              is_row.get("date", ""),
                "period":            is_row.get("period", ""),
                "fiscal_year":       is_row.get("fiscalYear", ""),
                "reported_currency": is_row.get("reportedCurrency", ""),
                # IS
                "revenue":          revenue,
                "gross_profit":     gross,
                "operating_income": op_income,
                "net_income":       net_income,
                "eps_diluted":      _to_float(is_row.get("epsDiluted")),
                # Derived margins
                "gross_margin":     _safe_pct(gross,      revenue),
                "operating_margin": _safe_pct(op_income,  revenue),
                "net_margin":       _safe_pct(net_income, revenue),
                # CF
                "operating_cf":   op_cf,
                "fcf":            fcf,
                "capex":          capex,
                "buyback":        buyback,
                "dividends_paid": dividends,
                "fcf_margin":     _safe_pct(fcf, revenue),
                # D&A (IS preferred, fall back to CF)
                "depreciation_amortization": _to_float(
                    is_row.get("depreciationAndAmortization")
                    or cf.get("depreciationAndAmortization")
                ),
            }

            if sector == "bank":
                rec["net_interest_income"] = _to_float(is_row.get("netInterestIncome"))
                rec["interest_income"]     = _to_float(is_row.get("interestIncome"))
                rec["interest_expense"]    = _to_float(is_row.get("interestExpense"))
                rec["total_assets"]        = _to_float(bs.get("totalAssets"))
                rec["total_equity"]        = _to_float(bs.get("totalStockholdersEquity"))

            elif sector == "tech":
                rec["rd_expenses"]      = _to_float(is_row.get("researchAndDevelopmentExpenses"))
                rec["stock_based_comp"] = _to_float(cf.get("stockBasedCompensation"))

            elif sector == "energy":
                rec["total_debt"]       = _to_float(bs.get("totalDebt"))
                rec["cash_equivalents"] = _to_float(bs.get("cashAndCashEquivalents"))

            results.append(rec)

        return results

    def fetch_historical_earnings(
        self,
        symbol: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Fetch historical earnings (EPS actual vs estimate) for a symbol.

        FMP endpoint: GET /stable/earnings
          params: symbol, limit, apikey
        Returns list of dicts with keys: symbol, date, eps, epsEstimated,
          revenue, revenueEstimated, reportedCurrency, period
        """
        if not self.api_key:
            raise ValueError("FMP_API_KEY is not set")

        params = {
            "symbol": symbol,
            "limit": limit,
            "apikey": self.api_key,
        }
        url = f"{FMP_BASE_URL}/earnings"
        try:
            resp = self._http.get(url, params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("FMP earnings HTTP error for %s: %s", symbol, exc)
            return []

        data = resp.json()
        if isinstance(data, dict) and "error" in data:
            logger.warning("FMP earnings error for %s: %s", symbol, data["error"])
            return []

        return data if isinstance(data, list) else []

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalise_calendar_entry(raw: Dict[str, Any], company_map: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Convert a raw FMP calendar entry to our internal format.

        company_map: {ticker_upper: {"name": str, "tier": str, "country_code": str}}
        Returns None if the symbol is not in the target company list.
        """
        symbol: str = (raw.get("symbol") or "").upper()
        if not symbol:
            return None

        comp = company_map.get(symbol)
        if comp is None:
            return None

        # EPS
        eps_actual:   Optional[float] = _to_float(raw.get("eps"))
        eps_estimate: Optional[float] = _to_float(raw.get("epsEstimated"))

        # Revenue (FMP may use "revenue" or "revenueEstimated")
        rev_actual:   Optional[float] = _to_float(raw.get("revenue"))
        rev_estimate: Optional[float] = _to_float(raw.get("revenueEstimated"))

        # time field: "bmo", "amc", "--", or absent
        time_raw = (raw.get("time") or "").lower()
        if "bmo" in time_raw or "before" in time_raw:
            time_label = "BMO"
        elif "amc" in time_raw or "after" in time_raw:
            time_label = "AMC"
        else:
            time_label = "--"

        return {
            "symbol": symbol,
            "name": comp["name"],
            "tier": comp["tier"],
            "country_code": comp["country_code"],
            "date": raw.get("date", ""),
            "time": time_label,
            "fiscal_date_ending": raw.get("fiscalDateEnding", ""),
            "eps_estimate": eps_estimate,
            "eps_actual": eps_actual,
            "revenue_estimate": rev_estimate,
            "revenue_actual": rev_actual,
            "updated_from_date": raw.get("updatedFromDate", ""),
        }

    @staticmethod
    def normalise_historical_entry(raw: Dict[str, Any], comp: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a raw FMP historical earnings entry."""
        eps_actual:   Optional[float] = _to_float(raw.get("eps"))
        eps_estimate: Optional[float] = _to_float(raw.get("epsEstimated"))
        rev_actual:   Optional[float] = _to_float(raw.get("revenue"))
        rev_estimate: Optional[float] = _to_float(raw.get("revenueEstimated"))

        eps_surprise_pct: Optional[float] = None
        if eps_actual is not None and eps_estimate is not None and eps_estimate != 0:
            eps_surprise_pct = (eps_actual - eps_estimate) / abs(eps_estimate) * 100

        rev_surprise_pct: Optional[float] = None
        if rev_actual is not None and rev_estimate is not None and rev_estimate != 0:
            rev_surprise_pct = (rev_actual - rev_estimate) / abs(rev_estimate) * 100

        return {
            "symbol": (raw.get("symbol") or "").upper(),
            "name": comp["name"],
            "tier": comp["tier"],
            "date": raw.get("date", ""),
            "period": raw.get("period", ""),
            "eps_estimate": eps_estimate,
            "eps_actual": eps_actual,
            "eps_surprise_pct": eps_surprise_pct,
            "revenue_estimate": rev_estimate,
            "revenue_actual": rev_actual,
            "revenue_surprise_pct": rev_surprise_pct,
        }


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_pct(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Return numerator/denominator * 100, or None if inputs are invalid."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator * 100


fmp_earnings_provider = FMPEarningsProvider()
