import pytest

from goji.config import ConfigError, GenomeConfig, SportsGameOddsConfig


def test_sgo_config_requires_only_sgo_key(monkeypatch):
    monkeypatch.delenv("SPORTSGAMEODDS_API_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    with pytest.raises(ConfigError, match="SPORTSGAMEODDS_API_KEY"):
        SportsGameOddsConfig.from_env()


def test_genome_config_does_not_require_sgo_key(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
    monkeypatch.delenv("SPORTSGAMEODDS_API_KEY", raising=False)

    config = GenomeConfig.from_env()
    assert config.url == "https://example.supabase.co"
    assert config.service_role_key == "test-service-key"
