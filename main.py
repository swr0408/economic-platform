from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import time
import logging

from backend.config import settings
from backend.core.database import init_db, test_connection
from backend.core.redis_client import redis_client

# ルーターインポート
from backend.routers import (
    # 米国
    usa_fred, usa_bls, usa_bea, usa_housing, usa_employment,
    # 日本
    japan_cpi, japan_boj, japan_estat, japan_employment,
    # 英国
    uk_ons, uk_boe, uk_housing,
    # ユーロ圏
    euro_ecb, euro_eurostat,
    # ドイツ
    germany_destatis,
    # オーストラリア
    australia_abs, australia_rba,
    # ニュージーランド
    newzealand_stats, newzealand_rbnz,
    # カナダ
    canada_statcan, canada_boc,
    # 中国
    china_nbs, china_pboc,
    # スイス
    switzerland_fso, switzerland_snb,
    # 市場データ
    markets_stocks, markets_forex, markets_commodities,
    # その他機能
    calendar, earnings, news, ai_analysis, notifications
)

# ログ設定
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lifespan管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーション起動・終了時の処理"""
    # 起動時
    logger.info("🚀 Starting Economic Data Platform...")
    
    # データベース接続
    if await test_connection():
        logger.info("✅ Database connection established")
    else:
        logger.error("❌ Database connection failed")
        raise Exception("Database connection failed")
    
    # Redis接続
    try:
        await redis_client.connect()
        logger.info("✅ Redis connection established")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        raise
    
    # データベース初期化 (初回のみ)
    # await init_db()
    
    logger.info("✅ Application startup complete!")
    
    yield
    
    # 終了時
    logger.info("🛑 Shutting down Economic Data Platform...")
    await redis_client.close()
    logger.info("✅ Cleanup complete")

# FastAPIアプリケーション
app = FastAPI(
    title=settings.APP_NAME,
    description="Global Economic Data Platform API",
    version=settings.VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# ============================================
# Middleware
# ============================================

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Page", "X-Per-Page"]
)

# Gzip圧縮
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Trusted Host
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["yourdomain.com", "*.yourdomain.com"]
    )

# レスポンスタイム計測
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    # ログ出力
    logger.info(
        f"{request.method} {request.url.path} "
        f"- {response.status_code} - {process_time:.3f}s"
    )
    
    return response

# Rate Limiting (簡易版)
from collections import defaultdict
from datetime import datetime, timedelta

rate_limit_storage = defaultdict(list)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    now = datetime.now()
    
    # 過去1分のリクエストをフィルター
    rate_limit_storage[client_ip] = [
        req_time for req_time in rate_limit_storage[client_ip]
        if now - req_time < timedelta(minutes=1)
    ]
    
    # レート制限チェック
    if len(rate_limit_storage[client_ip]) >= settings.RATE_LIMIT_PER_MINUTE:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded. Please try again later."}
        )
    
    rate_limit_storage[client_ip].append(now)
    return await call_next(request)

# ============================================
# Exception Handlers
# ============================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "body": exc.body
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )

# ============================================
# Health Check
# ============================================

@app.get("/health", tags=["Health"])
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }

@app.get("/api/health", tags=["Health"])
async def api_health_check():
    """API詳細ヘルスチェック"""
    # データベース接続確認
    db_status = await test_connection()
    
    # Redis接続確認
    try:
        await redis_client.client.ping()
        redis_status = True
    except:
        redis_status = False
    
    return {
        "status": "healthy" if db_status and redis_status else "degraded",
        "checks": {
            "database": "ok" if db_status else "error",
            "redis": "ok" if redis_status else "error"
        },
        "version": settings.VERSION,
        "timestamp": datetime.now().isoformat()
    }

# ============================================
# Router Registration
# ============================================

# 米国
app.include_router(usa_fred.router, prefix="/api/usa/fred", tags=["USA - FRED"])
app.include_router(usa_bls.router, prefix="/api/usa/bls", tags=["USA - BLS"])
app.include_router(usa_bea.router, prefix="/api/usa/bea", tags=["USA - BEA"])
app.include_router(usa_housing.router, prefix="/api/usa/housing", tags=["USA - Housing"])
app.include_router(usa_employment.router, prefix="/api/usa/employment", tags=["USA - Employment"])

# 日本
app.include_router(japan_cpi.router, prefix="/api/japan/cpi", tags=["Japan - CPI"])
app.include_router(japan_boj.router, prefix="/api/japan/boj", tags=["Japan - BOJ"])
app.include_router(japan_estat.router, prefix="/api/japan/estat", tags=["Japan - e-Stat"])
app.include_router(japan_employment.router, prefix="/api/japan/employment", tags=["Japan - Employment"])

# 英国
app.include_router(uk_ons.router, prefix="/api/uk/ons", tags=["UK - ONS"])
app.include_router(uk_boe.router, prefix="/api/uk/boe", tags=["UK - BOE"])
app.include_router(uk_housing.router, prefix="/api/uk/housing", tags=["UK - Housing"])

# ユーロ圏
app.include_router(euro_ecb.router, prefix="/api/euro/ecb", tags=["Euro - ECB"])
app.include_router(euro_eurostat.router, prefix="/api/euro/eurostat", tags=["Euro - Eurostat"])

# ドイツ
app.include_router(germany_destatis.router, prefix="/api/germany", tags=["Germany"])

# オーストラリア
app.include_router(australia_abs.router, prefix="/api/australia/abs", tags=["Australia - ABS"])
app.include_router(australia_rba.router, prefix="/api/australia/rba", tags=["Australia - RBA"])

# ニュージーランド
app.include_router(newzealand_stats.router, prefix="/api/newzealand/stats", tags=["New Zealand - Stats"])
app.include_router(newzealand_rbnz.router, prefix="/api/newzealand/rbnz", tags=["New Zealand - RBNZ"])

# カナダ
app.include_router(canada_statcan.router, prefix="/api/canada/statcan", tags=["Canada - StatCan"])
app.include_router(canada_boc.router, prefix="/api/canada/boc", tags=["Canada - BOC"])

# 中国
app.include_router(china_nbs.router, prefix="/api/china/nbs", tags=["China - NBS"])
app.include_router(china_pboc.router, prefix="/api/china/pboc", tags=["China - PBOC"])

# スイス
app.include_router(switzerland_fso.router, prefix="/api/switzerland/fso", tags=["Switzerland - FSO"])
app.include_router(switzerland_snb.router, prefix="/api/switzerland/snb", tags=["Switzerland - SNB"])

# 市場データ
app.include_router(markets_stocks.router, prefix="/api/markets/stocks", tags=["Markets - Stocks"])
app.include_router(markets_forex.router, prefix="/api/markets/forex", tags=["Markets - Forex"])
app.include_router(markets_commodities.router, prefix="/api/markets/commodities", tags=["Markets - Commodities"])

# カレンダー
app.include_router(calendar.router, prefix="/api/calendar", tags=["Calendar"])
app.include_router(earnings.router, prefix="/api/earnings", tags=["Earnings"])

# ニュース
app.include_router(news.router, prefix="/api/news", tags=["News"])

# AI分析
app.include_router(ai_analysis.router, prefix="/api/ai", tags=["AI Analysis"])

# 通知
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])

# ============================================
# Root Endpoint
# ============================================

@app.get("/", tags=["Root"])
async def root():
    """APIルートエンドポイント"""
    return {
        "message": "Welcome to Economic Data Platform API",
        "version": settings.VERSION,
        "docs": "/api/docs",
        "health": "/health"
    }

# ============================================
# Startup Message
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║   🌍 Economic Data Platform API                         ║
    ║   Version: {settings.VERSION}                           ║
    ║   Environment: {settings.ENVIRONMENT}                   ║
    ║                                                          ║
    ║   📚 API Docs: http://localhost:{settings.PORT}/api/docs          ║
    ║   ❤️  Health: http://localhost:{settings.PORT}/health             ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
        log_level="debug" if settings.DEBUG else "info"
    )
