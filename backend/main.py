"""
Economic Platform API - メインエントリーポイント
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    from backend.config import SEASONALITY_DIR, SCREENSHOT_DIR, ALLOWED_ORIGINS
    from backend.routers.seasonality import router as seasonality_router
    from backend.routers.usa.fed_h15 import router as fed_h15_router
    from backend.routers.usa.nyfed import router as nyfed_router
    from backend.routers.usa.fred import router as fred_router
    from backend.routers.usa.cme_fedwatch import router as cme_fedwatch_router
    from backend.routers.usa.fomc_projections import router as fomc_projections_router
    from backend.routers.dashboard import router as dashboard_router
    from backend.routers.market import router as market_router
    from backend.routers.calendar import router as calendar_router
    from backend.routers.market_impact import router as market_impact_router
    from backend.services.usa.fomc_projections_scheduler import fomc_scheduler
    from backend.services.usa.policy_rate_scheduler import policy_rate_scheduler
    from backend.services.calendar.calendar_scheduler import calendar_scheduler
    from backend.scheduler import indicator_scheduler
    from backend.scheduler.fmp_release_scheduler import fmp_release_scheduler
    from backend.scheduler.dashboard_cache_scheduler import dashboard_cache_scheduler
except ImportError:
    from config import SEASONALITY_DIR, SCREENSHOT_DIR, ALLOWED_ORIGINS
    from routers.seasonality import router as seasonality_router
    from routers.usa.fed_h15 import router as fed_h15_router
    from routers.usa.nyfed import router as nyfed_router
    from routers.usa.fred import router as fred_router
    from routers.usa.cme_fedwatch import router as cme_fedwatch_router
    from routers.usa.fomc_projections import router as fomc_projections_router
    from routers.dashboard import router as dashboard_router
    from routers.market import router as market_router
    from routers.calendar import router as calendar_router
    from routers.market_impact import router as market_impact_router
    from services.usa.fomc_projections_scheduler import fomc_scheduler
    from services.usa.policy_rate_scheduler import policy_rate_scheduler
    from services.calendar.calendar_scheduler import calendar_scheduler
    from scheduler import indicator_scheduler
    from scheduler.fmp_release_scheduler import fmp_release_scheduler
    from scheduler.dashboard_cache_scheduler import dashboard_cache_scheduler

app = FastAPI(title="Economic Platform API", version="1.0.0")

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静的ファイル配信（シーズナリティ画像）
if SEASONALITY_DIR.exists():
    app.mount(
        "/static/seasonality",
        StaticFiles(directory=str(SEASONALITY_DIR)),
        name="seasonality",
    )

# 静的ファイル配信（スクリーンショット画像）
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    "/static/screenshots",
    StaticFiles(directory=str(SCREENSHOT_DIR)),
    name="screenshots",
)

# ルーター登録
app.include_router(seasonality_router)
app.include_router(fed_h15_router)
app.include_router(nyfed_router)
app.include_router(fred_router)
app.include_router(cme_fedwatch_router)
app.include_router(fomc_projections_router)
app.include_router(dashboard_router)
app.include_router(market_router)
app.include_router(calendar_router)
app.include_router(market_impact_router)


@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "ok", "message": "Server is running"}


@app.get("/api/health")
async def api_health_check():
    """API ヘルスチェックエンドポイント"""
    return {"status": "ok", "message": "API is running"}


@app.get("/api/scheduler/status")
async def scheduler_status():
    """スケジューラーのステータスを取得"""
    try:
        return {
            "status": "ok",
            "indicator_scheduler": indicator_scheduler.get_status()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@app.on_event("startup")
async def startup_event():
    """起動時の処理"""
    print(f"SEASONALITY_DIR: {SEASONALITY_DIR}")
    print(f"SEASONALITY_DIR exists: {SEASONALITY_DIR.exists()}")

    # FOMC関連スケジューラーを開始
    try:
        fomc_scheduler.start()
        print("FOMC Projections Scheduler started successfully")
    except Exception as e:
        print(f"Warning: Could not start FOMC Projections Scheduler: {e}")

    try:
        policy_rate_scheduler.start()
        print("Policy Rate Scheduler started successfully")
    except Exception as e:
        print(f"Warning: Could not start Policy Rate Scheduler: {e}")

    # 経済指標スケジューラーを開始
    try:
        indicator_scheduler.start()
        print("Economic Indicator Scheduler started successfully")
    except Exception as e:
        print(f"Warning: Could not start Economic Indicator Scheduler: {e}")

    # 経済カレンダースケジューラーを開始
    try:
        calendar_scheduler.start()
        print("Calendar Scheduler started successfully")
    except Exception as e:
        print(f"Warning: Could not start Calendar Scheduler: {e}")

    # FMP発表日ベーススケジューラーを開始
    try:
        fmp_release_scheduler.start()
        print("FMP Release Scheduler started successfully")
    except Exception as e:
        print(f"Warning: Could not start FMP Release Scheduler: {e}")

    # ダッシュボードキャッシュスケジューラーを開始
    try:
        dashboard_cache_scheduler.start()
        print("Dashboard Cache Scheduler started successfully")
    except Exception as e:
        print(f"Warning: Could not start Dashboard Cache Scheduler: {e}")

    print("=" * 60)
    print("Economic Platform API started")
    print("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """シャットダウン時の処理"""
    try:
        fomc_scheduler.shutdown()
    except Exception as e:
        print(f"Warning: Error shutting down FOMC Scheduler: {e}")

    try:
        policy_rate_scheduler.shutdown()
    except Exception as e:
        print(f"Warning: Error shutting down Policy Rate Scheduler: {e}")

    try:
        indicator_scheduler.shutdown()
    except Exception as e:
        print(f"Warning: Error shutting down Indicator Scheduler: {e}")

    try:
        calendar_scheduler.stop()
    except Exception as e:
        print(f"Warning: Error shutting down Calendar Scheduler: {e}")

    try:
        fmp_release_scheduler.shutdown()
    except Exception as e:
        print(f"Warning: Error shutting down FMP Release Scheduler: {e}")

    try:
        dashboard_cache_scheduler.shutdown()
    except Exception as e:
        print(f"Warning: Error shutting down Dashboard Cache Scheduler: {e}")

    print("Economic Platform API shutdown complete")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('backend.main:app', host='0.0.0.0', port=8000, reload=True)
