from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql://agentespacio:agentespacio@db:5432/agentespacio_db"
    postgres_user: str = "agentespacio"
    postgres_password: str = "agentespacio"
    postgres_db: str = "agentespacio_db"
    postgres_host: str = "db"
    postgres_port: int = 5432
    
    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    
    # Celery
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"
    
    # API
    api_host: str = "0.0.0.0"

    secret_key: str = "some-sort-of-secret"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
