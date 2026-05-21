from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    app_name: str = Field(default='cosmetic-support', alias='APP_NAME')
    app_env: Literal['development', 'staging', 'production'] = Field(default='development', alias='APP_ENV')
    app_host: str = Field(default='0.0.0.0', alias='APP_HOST')
    app_port: int = Field(default=8000, alias='APP_PORT', ge=1, le=65535)
    log_level: str = Field(default='INFO', alias='LOG_LEVEL')

    bot_token: SecretStr = Field(alias='BOT_TOKEN')
    telegram_api_id: int = Field(alias='TELEGRAM_API_ID', gt=0)
    telegram_api_hash: SecretStr = Field(alias='TELEGRAM_API_HASH')
    telegram_client_name: str = Field(default='cosmetic_client', alias='TELEGRAM_CLIENT_NAME')

    operator_ids: list[int] = Field(default_factory=list, alias='OPERATOR_IDS')
    incoming_debounce_seconds: int = Field(default=3, alias='INCOMING_DEBOUNCE_SECONDS', ge=0, le=60)

    openai_api_key: SecretStr = Field(alias='OPENAI_API_KEY')
    openai_model: str = Field(default='gpt-4.1-mini', alias='OPENAI_MODEL')

    database_url: str = Field(alias='DATABASE_URL')
    redis_url: str = Field(alias='REDIS_URL')

    @field_validator('operator_ids', mode='before')
    @classmethod
    def parse_operator_ids(cls, value: str | list[int] | None) -> list[int]:
        if value is None or value == '':
            return []
        if isinstance(value, list):
            return [int(item) for item in value]
        return [int(item.strip()) for item in value.split(',') if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
