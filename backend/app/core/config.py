"""全局配置：环境变量(.env)优先，运行期配置走 system_configs 表（里程碑7热更新）。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BAAS_", extra="ignore")

    app_name: str = "Business_Attribution_Analysis_System"

    db_url: str = "sqlite+aiosqlite:///backend/baas_dev.db"

    jwt_secret: str = "dev-secret-change-me"
    jwt_alg: str = "HS256"
    jwt_expires_min: int = 120

    public_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:5173"

    auth_base_url: str = "http://127.0.0.1:9001"
    auth_client_id: str = "baas-web"
    auth_client_secret: str = "baas-web-secret"

    llm_provider: str = "mock"  # mock | openai(兼容 SiliconFlow 等)
    llm_base_url: str = "http://127.0.0.1:9002"
    llm_model: str = "mock-attribution"
    llm_api_key: str = "mock-key"


@lru_cache
def get_settings() -> Settings:
    return Settings()
