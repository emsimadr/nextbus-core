"""Tests for config loading."""

import os
import pytest
from src.config import load_config, AppConfig, BoardItemConfig


@pytest.fixture()
def valid_config_yaml(tmp_path):
    """Write a minimal valid config.yaml and return its path."""
    content = """\
cache_ttl: 15
stale_max_age: 120

stops:
  - key: "route_77"
    label: "77 - Harvard"
    route_id: "77"
    stop_id: "2261"
    direction_id: 1
    walk_minutes: 4
"""
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return str(p)


@pytest.fixture()
def two_stops_config_yaml(tmp_path):
    """Config with two stops."""
    content = """\
stops:
  - key: "route_77"
    label: "77 - Harvard"
    route_id: "77"
    stop_id: "2261"
    direction_id: 1
    walk_minutes: 4
  - key: "route_350"
    label: "350 - Alewife"
    route_id: "350"
    stop_id: "2281"
    direction_id: 1
    walk_minutes: 4
"""
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return str(p)


class TestLoadConfig:
    def test_loads_valid_config(self, valid_config_yaml):
        config = load_config(valid_config_yaml)
        assert config.cache_ttl == 15
        assert config.stale_max_age == 120
        assert len(config.stops) == 1
        assert config.stops[0].key == "route_77"
        assert config.stops[0].label == "77 - Harvard"
        assert config.stops[0].route_id == "77"
        assert config.stops[0].stop_id == "2261"
        assert config.stops[0].direction_id == 1
        assert config.stops[0].walk_minutes == 4

    def test_defaults_applied(self, tmp_path):
        content = """\
stops:
  - key: "test"
    label: "Test"
    route_id: "1"
    stop_id: "100"
    direction_id: 0
"""
        p = tmp_path / "config.yaml"
        p.write_text(content)
        config = load_config(str(p))
        assert config.cache_ttl == 20
        assert config.stale_max_age == 300
        assert config.mbta_base_url == "https://api-v3.mbta.com"
        assert config.stops[0].walk_minutes == 0

    def test_env_overrides_secrets(self, valid_config_yaml, monkeypatch):
        monkeypatch.setenv("MBTA_API_KEY", "test-key-123")
        monkeypatch.setenv("API_KEY", "my-secret")
        config = load_config(valid_config_yaml)
        assert config.mbta_api_key == "test-key-123"
        assert config.api_key == "my-secret"

    def test_secrets_none_when_not_set(self, valid_config_yaml, monkeypatch):
        monkeypatch.delenv("MBTA_API_KEY", raising=False)
        monkeypatch.delenv("API_KEY", raising=False)
        config = load_config(valid_config_yaml)
        assert config.mbta_api_key is None
        assert config.api_key is None

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yaml")

    def test_missing_stops_raises(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text("cache_ttl: 10\n")
        with pytest.raises(Exception):  # ValidationError
            load_config(str(p))

    def test_empty_stops_raises(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text("stops: []\n")
        with pytest.raises(Exception):  # ValidationError
            load_config(str(p))

    def test_duplicate_keys_raises(self, tmp_path):
        content = """\
stops:
  - key: "same"
    label: "A"
    route_id: "1"
    stop_id: "100"
    direction_id: 0
  - key: "same"
    label: "B"
    route_id: "2"
    stop_id: "200"
    direction_id: 1
"""
        p = tmp_path / "config.yaml"
        p.write_text(content)
        with pytest.raises(Exception, match="Duplicate"):
            load_config(str(p))

    def test_invalid_direction_id_raises(self, tmp_path):
        content = """\
stops:
  - key: "test"
    label: "Test"
    route_id: "1"
    stop_id: "100"
    direction_id: 5
"""
        p = tmp_path / "config.yaml"
        p.write_text(content)
        with pytest.raises(Exception):
            load_config(str(p))

    def test_missing_required_fields_raises(self, tmp_path):
        content = """\
stops:
  - key: "test"
"""
        p = tmp_path / "config.yaml"
        p.write_text(content)
        with pytest.raises(Exception):
            load_config(str(p))

    def test_get_stop_by_key(self, two_stops_config_yaml):
        config = load_config(two_stops_config_yaml)
        stop = config.get_stop("route_350")
        assert stop is not None
        assert stop.route_id == "350"

    def test_get_stop_not_found(self, two_stops_config_yaml):
        config = load_config(two_stops_config_yaml)
        assert config.get_stop("nonexistent") is None

    def test_config_path_from_env(self, valid_config_yaml, monkeypatch):
        monkeypatch.setenv("CONFIG_PATH", valid_config_yaml)
        config = load_config()
        assert len(config.stops) == 1

    def test_mbta_base_url_from_yaml(self, tmp_path):
        content = """\
mbta_base_url: "http://localhost:9999"
stops:
  - key: "test"
    label: "Test"
    route_id: "1"
    stop_id: "100"
    direction_id: 0
"""
        p = tmp_path / "config.yaml"
        p.write_text(content)
        config = load_config(str(p))
        assert config.mbta_base_url == "http://localhost:9999"
