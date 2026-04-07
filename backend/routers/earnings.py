"""Earnings API router."""

from fastapi import APIRouter, Depends, HTTPException

try:
    from backend.services.earnings.earnings_service import earnings_service
    from backend.core.auth.dependencies import require_role
    from backend.core.auth.models import ROLE_MASTER
except ImportError:
    from services.earnings.earnings_service import earnings_service
    from core.auth.dependencies import require_role
    from core.auth.models import ROLE_MASTER

# master ロール要求の依存オブジェクト
_require_master = require_role(ROLE_MASTER)


router = APIRouter(prefix="/api/earnings", tags=["Earnings"])


@router.get("/countries")
def get_earnings_countries():
    return earnings_service.list_countries()


@router.get("/calendar/all")
def get_earnings_calendar_all():
    """Global calendar merged from all countries."""
    return earnings_service.get_calendar_all()


@router.get("/{country_code}/calendar")
def get_earnings_calendar(country_code: str):
    try:
        return earnings_service.get_calendar(country_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{country_code}/data")
def get_earnings_data(country_code: str):
    try:
        return earnings_service.get_data(country_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{country_code}/status")
def get_earnings_status(country_code: str):
    try:
        return earnings_service.get_status(country_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{country_code}/{ticker}/financials")
def get_earnings_financials(country_code: str, ticker: str):
    """Quarterly financials (IS+CF+BS merged) for a single ticker."""
    try:
        return earnings_service.get_financials(country_code, ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{country_code}/cache")
def invalidate_earnings_cache(
    country_code: str,
    _master = Depends(_require_master),
):
    """Earnings キャッシュを削除 (master 限定)."""
    try:
        return earnings_service.invalidate_cache(country_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
