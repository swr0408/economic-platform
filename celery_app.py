from celery import Celery
from celery.schedules import crontab
from backend.config import settings
import os

# Celeryアプリ
celery_app = Celery(
    'economic_platform',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# 設定
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # パフォーマンス
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    
    # リトライ
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,
    task_max_retries=3,
    
    # ルーティング
    task_routes={
        'tasks.markets.*': {'queue': 'markets'},
        'tasks.ai.*': {'queue': 'ai'},
        'tasks.notifications.*': {'queue': 'notifications'},
    },
)

# Beat Schedule (340スケジューラー)
celery_app.conf.beat_schedule = {
    # === 米国 経済指標 ===
    'fetch-us-cpi-monthly': {
        'task': 'tasks.usa.fetch_cpi',
        'schedule': crontab(day_of_month='15', hour=13, minute=30),  # UTC
        'kwargs': {'source': 'BLS'},
    },
    'fetch-us-unemployment': {
        'task': 'tasks.usa.fetch_unemployment',
        'schedule': crontab(day_of_month='1-7', day_of_week=5, hour=13, minute=30),
    },
    'fetch-us-gdp': {
        'task': 'tasks.usa.fetch_gdp',
        'schedule': crontab(day_of_month='25-31', hour=13, minute=30),
    },
    
    # === 日本 経済指標 ===
    'fetch-japan-cpi': {
        'task': 'tasks.japan.fetch_cpi',
        'schedule': crontab(day_of_month='25-28', hour=23, minute=30),  # JST 8:30
    },
    'fetch-japan-tankan': {
        'task': 'tasks.japan.fetch_tankan',
        'schedule': crontab(month_of_year='4,7,10,12', day_of_month='1', hour=23, minute=50),
    },
    
    # === 市場データ (高頻度) ===
    'fetch-stock-prices-1min': {
        'task': 'tasks.markets.fetch_stock_prices',
        'schedule': crontab(minute='*/1', day_of_week='mon-fri'),
        'kwargs': {'symbols': ['SPY', 'QQQ', 'DIA'], 'interval': '1m'},
    },
    'fetch-forex-rates': {
        'task': 'tasks.markets.fetch_forex',
        'schedule': crontab(minute='*/5'),
        'kwargs': {'pairs': ['EURUSD', 'USDJPY', 'GBPUSD']},
    },
    'fetch-commodities': {
        'task': 'tasks.markets.fetch_commodities',
        'schedule': crontab(minute='*/10'),
        'kwargs': {'symbols': ['GC=F', 'CL=F', 'SI=F']},  # 金、原油、銀
    },
    
    # === AI分析 ===
    'ai-daily-pattern-analysis': {
        'task': 'tasks.ai.analyze_daily_patterns',
        'schedule': crontab(hour=3, minute=0),  # 毎日深夜3時
    },
    'ai-weekly-report': {
        'task': 'tasks.ai.generate_weekly_report',
        'schedule': crontab(day_of_week=0, hour=4, minute=0),  # 日曜 4時
    },
    
    # === ニュース収集 ===
    'fetch-twitter-headlines': {
        'task': 'tasks.news.fetch_twitter',
        'schedule': crontab(minute='*/15'),
    },
    
    # === カレンダー更新 ===
    'update-economic-calendar': {
        'task': 'tasks.calendar.update_events',
        'schedule': crontab(hour='*/6'),  # 6時間ごと
    },
    'update-earnings-calendar': {
        'task': 'tasks.calendar.update_earnings',
        'schedule': crontab(hour=1, minute=0),  # 毎日深夜1時
    },
    
    # === キャッシュ管理 ===
    'cleanup-expired-cache': {
        'task': 'tasks.maintenance.cleanup_cache',
        'schedule': crontab(hour=2, minute=0),
    },
    
    # ... 残り300個のスケジュール ...
}

# タスク自動検出
celery_app.autodiscover_tasks([
    'backend.services.usa',
    'backend.services.japan',
    'backend.services.markets',
    'backend.services.ai',
    'backend.services.notifications',
])

if __name__ == '__main__':
    celery_app.start()
