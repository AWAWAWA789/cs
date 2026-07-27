"""Configuration management for the CSQAQ quant framework."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    api_token: str
    base_url: str
    cache_path: str
    sub_index_id: str
    sub_index_name: str
    default_period: str

    def __init__(self):
        object.__setattr__(self, "api_token", os.getenv("CSQAQ_API_TOKEN", ""))
        object.__setattr__(
            self, "base_url", os.getenv("CSQAQ_BASE_URL", "https://api.csqaq.com/api/v1")
        )
        object.__setattr__(self, "cache_path", os.getenv("CSQAQ_CACHE_PATH", "./data/cache"))
        object.__setattr__(self, "sub_index_id", os.getenv("SUB_INDEX_ID", ""))
        object.__setattr__(self, "sub_index_name", os.getenv("SUB_INDEX_NAME", "手套"))
        object.__setattr__(self, "default_period", os.getenv("DEFAULT_PERIOD", "4hour"))

    def validate(self) -> None:
        """Validate that required settings are present."""
        if not self.api_token:
            raise ValueError("CSQAQ_API_TOKEN is required")
