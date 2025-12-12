"""
Economic Platform API - メインエントリーポイント
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    from backend.config import SEASONALITY_DIR, ALLOWED_ORIGINS
    from backend.routers.seasonality import router as seasonality_router
except ImportError:
    from config import SEASONALITY_DIR, ALLOWED_ORIGINS
    from routers.seasonality import router as seasonality_router

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

# ルーター登録
app.include_router(seasonality_router)


@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "ok", "message": "Server is running"}


@app.get("/api/health")
async def api_health_check():
    """API ヘルスチェックエンドポイント"""
    return {"status": "ok", "message": "API is running"}


@app.on_event("startup")
async def startup_event():
    """起動時の処理"""
    print(f"SEASONALITY_DIR: {SEASONALITY_DIR}")
    print(f"SEASONALITY_DIR exists: {SEASONALITY_DIR.exists()}")
    print("=" * 60)
    print("Economic Platform API started")
    print("=" * 60)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('backend.main:app', host='0.0.0.0', port=8000, reload=True)
