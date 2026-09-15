from dataclasses import dataclass
import os


class ConfigError(RuntimeError):
    pass


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class SportsGameOddsConfig:
    api_key: str
    base_url: str = "https://api.sportsgameodds.com/v2"
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "SportsGameOddsConfig":
        return cls(api_key=_required_env("SPORTSGAMEODDS_API_KEY"))


@dataclass(frozen=True)
class GenomeConfig:
    url: str
    service_role_key: str
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "GenomeConfig":
        return cls(
            url=_required_env("SUPABASE_URL").rstrip("/"),
            service_role_key=_required_env("SUPABASE_SERVICE_ROLE_KEY"),
        )
