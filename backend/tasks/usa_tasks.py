"""
USA経済データ取得タスク
Celery Beatによる定期実行用
"""
import sys
import os
from datetime import datetime

# パス設定
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tasks.celery_app import celery_app


@celery_app.task(
    name="tasks.usa_tasks.refresh_policy_rate",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def refresh_policy_rate(self):
    """
    政策金利データを更新
    1. Federal Reserve APIからデータ取得
    2. PostgreSQLに保存
    3. Redisキャッシュを更新
    毎時実行
    """
    try:
        from services.usa.fed_h15_service import fed_h15_service

        print(f"[{datetime.now().isoformat()}] Starting policy rate refresh...")

        success = fed_h15_service.refresh_cache()

        if success:
            status = fed_h15_service.get_cache_status()
            print(f"[{datetime.now().isoformat()}] Policy rate refreshed successfully")
            return {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "cache_status": status
            }
        else:
            raise Exception("Failed to refresh policy rate")

    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Error refreshing policy rate: {e}")
        raise self.retry(exc=e)


@celery_app.task(name="tasks.usa_tasks.health_check")
def health_check():
    """
    ヘルスチェックタスク
    Redis/DB接続とキャッシュ状態を確認
    """
    try:
        from services.usa.fed_h15_service import fed_h15_service
        from core.redis_client import redis_client
        from core.database import test_connection

        # Redis接続確認
        redis_ok = redis_client.ping()

        # DB接続確認
        db_ok = test_connection()

        # キャッシュ状態
        cache_status = fed_h15_service.get_cache_status()

        result = {
            "status": "healthy" if redis_ok and db_ok else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "redis": "connected" if redis_ok else "disconnected",
            "database": "connected" if db_ok else "disconnected",
            "policy_rate_cache": cache_status
        }

        print(f"[{datetime.now().isoformat()}] Health check: {result}")
        return result

    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


@celery_app.task(
    name="tasks.usa_tasks.refresh_fedwatch",
    bind=True,
    max_retries=3,
    default_retry_delay=120
)
def refresh_fedwatch(self):
    """
    CME FedWatch スクリーンショットを更新
    Playwrightでスクリーンショットを取得
    30分ごとに実行
    """
    try:
        from services.usa.cme_fedwatch_screenshot_service import cme_fedwatch_screenshot_service

        print(f"[{datetime.now().isoformat()}] Starting FedWatch screenshot capture...")

        result = cme_fedwatch_screenshot_service.get_screenshot(force_refresh=True)

        if result.get("image_url"):
            status = cme_fedwatch_screenshot_service.get_cache_status()
            print(f"[{datetime.now().isoformat()}] FedWatch screenshot captured: {result.get('source')}")
            return {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "source": result.get("source"),
                "cache_status": status
            }
        else:
            raise Exception(f"Failed to capture FedWatch screenshot: {result.get('error')}")

    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Error capturing FedWatch screenshot: {e}")
        raise self.retry(exc=e)


@celery_app.task(name="tasks.usa_tasks.refresh_all_usa_data")
def refresh_all_usa_data():
    """
    USAの全経済データを一括更新
    手動実行または日次バッチ用
    """
    results = {}

    # 政策金利
    try:
        policy_result = refresh_policy_rate()
        results["policy_rate"] = policy_result
    except Exception as e:
        results["policy_rate"] = {"status": "error", "error": str(e)}

    # FedWatch
    try:
        fedwatch_result = refresh_fedwatch()
        results["fedwatch"] = fedwatch_result
    except Exception as e:
        results["fedwatch"] = {"status": "error", "error": str(e)}

    # 将来追加予定：
    # - CPI (インフレ)
    # - 雇用統計
    # - GDP
    # - 住宅データ

    return {
        "status": "completed",
        "timestamp": datetime.now().isoformat(),
        "results": results
    }
