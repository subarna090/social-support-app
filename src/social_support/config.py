"""Application settings, read from environment variables or a local ``.env`` file."""

from decimal import Decimal
from functools import lru_cache

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./data/app.db"
    caseworker_passcode: SecretStr | None = None
    assessor: str = "income_rule"
    rule_threshold_aed: Decimal = Decimal("2000")
    rule_band_upper_aed: Decimal = Decimal("2500")
    api_base_url: str = "http://127.0.0.1:8000"

    @model_validator(mode="after")
    def _band_not_below_threshold(self) -> "Settings":
        if self.rule_band_upper_aed < self.rule_threshold_aed:
            raise ValueError("RULE_BAND_UPPER_AED must not be lower than RULE_THRESHOLD_AED")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
