from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Economic Data Platform"
    VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 2
    
    # Database
    DATABASE_URL: str
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    
    # Redis
    REDIS_URL: str
    REDIS_MAX_CONNECTIONS: int = 50
    
    # Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # External APIs
    FRED_API_KEY: str = ""
    BLS_API_KEY: str = ""
    BEA_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    TWITTER_BEARER_TOKEN: str = ""
    ALPHA_VANTAGE_API_KEY: str = ""
    
    # Notifications
    DISCORD_WEBHOOK_URL: str = ""
    LINE_CHANNEL_ACCESS_TOKEN: str = ""
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # Cache
    CACHE_TTL_SHORT: int = 60           # 1分
    CACHE_TTL_MEDIUM: int = 3600        # 1時間
    CACHE_TTL_LONG: int = 86400         # 1日
    
    # Monitoring
    SENTRY_DSN: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
