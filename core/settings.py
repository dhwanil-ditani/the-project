from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Literal

class Settings(BaseSettings):
    app_env: Literal["dev", "prod", "testing"] = Field(default="dev", validation_alias="APP_ENV")
    
    # DB URL configs
    database_url: str | None = None
    
    # Optional override via .env
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

class DevSettings(Settings):
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/postgres")

class ProdSettings(Settings):
    database_url: str = Field(default="postgresql+asyncpg://user:password@localhost:5432/prod_db")

class TestSettings(Settings):
    database_url: str = Field(default="sqlite+aiosqlite:///./test.db")

def get_settings() -> Settings:
    base_settings = Settings()
    if base_settings.app_env == "prod":
        return ProdSettings()
    elif base_settings.app_env == "testing":
        return TestSettings()
    return DevSettings()

settings = get_settings()
