from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WIFI_", extra="ignore")

    sample_rate_hz: int = 20
    window_seconds: int = 12
    waves_history_samples: int = 240

    presence_variance_threshold: float = 0.02
    presence_debounce_samples: int = 6

    heartbeat_low_bpm: int = 48
    heartbeat_high_bpm: int = 132

    ws_emit_hz: int = 5
    trusted_hosts: str = "localhost,127.0.0.1,testserver"

    @property
    def trusted_hosts_list(self) -> list[str]:
        return [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return AppConfig()
