"""
Configuration loading for bus-tracker.

Loads non-secret settings from config.yaml, secrets from environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, model_validator


class BoardItemConfig(BaseModel):
    """One configured bus stop."""

    key: str
    label: str
    route_id: str
    stop_id: str
    direction_id: int = Field(ge=0, le=1)
    walk_minutes: int = Field(default=0, ge=0)


class AppConfig(BaseModel):
    """Application configuration. Secrets come from env vars, rest from YAML."""

    # Secrets (from environment only)
    mbta_api_key: Optional[str] = None
    api_key: Optional[str] = None

    # MBTA settings
    mbta_base_url: str = "https://api-v3.mbta.com"

    # Cache settings
    cache_ttl: int = Field(default=20, ge=1)
    stale_max_age: int = Field(default=300, ge=0)

    # Configured stops
    stops: list[BoardItemConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_keys(self) -> "AppConfig":
        keys = [stop.key for stop in self.stops]
        duplicates = [k for k in keys if keys.count(k) > 1]
        if duplicates:
            raise ValueError(f"Duplicate stop keys: {set(duplicates)}")
        return self

    def get_stop(self, key: str) -> BoardItemConfig | None:
        """Look up a stop config by key."""
        for stop in self.stops:
            if stop.key == key:
                return stop
        return None


def load_config(config_path: str | None = None) -> AppConfig:
    """
    Load configuration from YAML file + environment variables.

    Args:
        config_path: Path to config.yaml. If None, reads CONFIG_PATH env var
                     (default: config.yaml in current directory).

    Returns:
        Validated AppConfig instance.
    """
    if config_path is None:
        config_path = os.environ.get("CONFIG_PATH", "config.yaml")

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raw = {}

    # Inject secrets from environment (never from YAML)
    mbta_api_key = os.environ.get("MBTA_API_KEY")
    api_key = os.environ.get("API_KEY")

    config_data = {
        **raw,
        "mbta_api_key": mbta_api_key,
        "api_key": api_key,
    }

    return AppConfig(**config_data)
