from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "warden"
    app_env: str = "local"
    database_url: str = "file:/data/warden.db?mode=rwc"
    history_limit: int = 5
    llm_provider: str = "heuristic"
    llm_api_url: str = "https://api.groq.com/openai/v1/chat/completions"
    llm_api_key: str = ""
    llm_model: str = "llama-3.1-8b-instant"
    orchestrator_base_url: str = "http://orchestrator-mock:8001"
    notifier_base_url: str = "http://notifier-mock:8002"
    request_timeout_seconds: float = 5.0
    productive_environments: str = "prod,production"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", env_prefix="WARDEN_", extra="ignore")

    @property
    def productive_environment_names(self) -> set[str]:
        return {item.strip().lower() for item in self.productive_environments.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
