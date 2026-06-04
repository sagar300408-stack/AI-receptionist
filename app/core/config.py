import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl

class Settings(BaseSettings):
    PROJECT_NAME: str = "Tvira Business Discovery Engine"
    API_V1_STR: str = "/api/v1"
    
    # Database
    # Default to local SQLite fallback if PostgreSQL url is not configured
    DATABASE_URL: str = "sqlite+aiosqlite:///./tvira_business.db"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]
    
    # Session lifecycle configs
    SESSION_EXPIRE_HOURS: int = 24
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

settings = Settings()
