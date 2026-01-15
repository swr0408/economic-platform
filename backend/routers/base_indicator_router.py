"""
経済指標ルーター生成ユーティリティ

全ての経済指標ルーターで共通のエンドポイント構造を提供する。

使用方法:
    from routers.base_indicator_router import create_indicator_router
    from services.japan.japan_cgpi_food_agriculture_service import japan_cgpi_food_agriculture_service

    router = create_indicator_router(
        prefix="/api/japan/cgpi-food-agriculture",
        service=japan_cgpi_food_agriculture_service,
        tags=["Japan Price"],
        description="企業物価指数：飲食料品・農林水産物",
    )

生成されるエンドポイント:
    GET     /                   - データ取得
    GET     /cache/status       - キャッシュステータス取得
    POST    /cache/refresh      - キャッシュ強制更新
    DELETE  /cache              - キャッシュ無効化
"""
from typing import Any, List, Optional
from fastapi import APIRouter, Query


def create_indicator_router(
    prefix: str,
    service: Any,
    tags: List[str],
    description: str = "Economic indicator",
    get_data_method: str = "get_data",
    get_cache_status_method: str = "get_cache_status",
    invalidate_cache_method: str = "invalidate_cache",
) -> APIRouter:
    """
    経済指標用のルーターを生成

    Args:
        prefix: APIプレフィックス（例: "/api/japan/cgpi-food-agriculture"）
        service: サービスインスタンス
        tags: OpenAPI用タグ
        description: 指標の説明（ドキュメント用）
        get_data_method: データ取得メソッド名
        get_cache_status_method: キャッシュステータス取得メソッド名
        invalidate_cache_method: キャッシュ無効化メソッド名

    Returns:
        設定済みのAPIRouter
    """
    router = APIRouter(prefix=prefix, tags=tags)

    @router.get("")
    async def get_data(
        force_refresh: bool = Query(False, description="Force refresh from source")
    ):
        """
        データを取得

        - **force_refresh**: trueの場合、キャッシュを無視してデータを再取得
        """
        method = getattr(service, get_data_method)
        return method(force_refresh=force_refresh)

    # docstringを動的に設定
    get_data.__doc__ = f"""
    {description}データを取得

    - **force_refresh**: trueの場合、キャッシュを無視してデータを再取得
    """

    @router.get("/cache/status")
    async def get_cache_status():
        """キャッシュステータスを取得"""
        method = getattr(service, get_cache_status_method)
        return method()

    @router.post("/cache/refresh")
    async def refresh_cache():
        """キャッシュを強制更新"""
        method = getattr(service, get_data_method)
        result = method(force_refresh=True)
        return {
            "success": True,
            "message": "Cache refreshed",
            "data_count": len(result.get("data", [])),
            "latest": result.get("latest"),
        }

    @router.delete("/cache")
    async def invalidate_cache():
        """キャッシュを無効化"""
        method = getattr(service, invalidate_cache_method)
        success = method()
        return {
            "success": success,
            "message": "Cache invalidated" if success else "Failed to invalidate cache"
        }

    return router


def create_indicator_routers_from_registry(
    registry_configs: List[Any],
    prefix_template: str = "/api/{country}/{indicator_slug}",
    default_tags: Optional[List[str]] = None,
) -> List[APIRouter]:
    """
    レジストリ設定から複数のルーターを一括生成

    Args:
        registry_configs: IndicatorConfig のリスト
        prefix_template: プレフィックステンプレート
        default_tags: デフォルトのタグ

    Returns:
        生成されたルーターのリスト
    """
    import importlib

    routers = []
    for config in registry_configs:
        try:
            # サービスを動的インポート
            module_paths = [
                f"backend.{config.service_module}",
                config.service_module,
            ]

            service = None
            for module_path in module_paths:
                try:
                    module = importlib.import_module(module_path)
                    service = getattr(module, config.service_instance)
                    break
                except ImportError:
                    continue

            if service is None:
                print(f"Failed to import service: {config.service_module}")
                continue

            # プレフィックスを生成
            indicator_slug = config.name_en.lower().replace(" ", "-").replace("&", "and")

            router = create_indicator_router(
                prefix=f"/api/{indicator_slug}",
                service=service,
                tags=default_tags or [config.category.value],
                description=config.name,
            )
            routers.append(router)

        except Exception as e:
            print(f"Error creating router for {config.name}: {e}")
            continue

    return routers
