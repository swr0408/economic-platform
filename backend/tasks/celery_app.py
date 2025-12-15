"""
Celery アプリケーション設定
定期的なデータ取得タスクのスケジューリング
"""
import os
from celery import Celery
from celery.schedules import crontab

# Redis URL（環境変数から取得、デフォルトはローカル）
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Celeryアプリケーションを作成
celery_app = Celery(
    "economic_platform",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks.usa_tasks"]
)

# Celery設定
celery_app.conf.update(
    # タイムゾーン
    timezone="UTC",

    # タスクのシリアライズ
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # タスクの有効期限（1日）
    result_expires=86400,

    # タスクの再試行設定
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # ワーカー設定
    worker_prefetch_multiplier=1,
    worker_concurrency=2,
)

# Celery Beat スケジュール設定
celery_app.conf.beat_schedule = {
    # 政策金利データ：1時間ごとに更新
    "refresh-policy-rate-hourly": {
        "task": "tasks.usa_tasks.refresh_policy_rate",
        "schedule": crontab(minute=0),  # 毎時0分
        "options": {"queue": "economic_data"}
    },

    # CME FedWatch：30分ごとに更新
    "refresh-fedwatch": {
        "task": "tasks.usa_tasks.refresh_fedwatch",
        "schedule": crontab(minute="*/30"),  # 30分ごと
        "options": {"queue": "economic_data"}
    },

    # ヘルスチェック：5分ごと
    "health-check": {
        "task": "tasks.usa_tasks.health_check",
        "schedule": crontab(minute="*/5"),  # 5分ごと
        "options": {"queue": "economic_data"}
    },
}

# デフォルトキュー
celery_app.conf.task_default_queue = "economic_data"


if __name__ == "__main__":
    celery_app.start()
