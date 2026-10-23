from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict
from stonks.core.settings import HttpConfig, StonksSettings, config_files


class UniverseConfig(BaseModel):
    constituents_url: str
    symbol_overrides: dict[str, str]
    ignored: dict[str, str]
    min_instruments: int = Field(gt=0)


class YahooConfig(BaseModel):
    search_url: str
    chart_url: str
    min_interval_seconds: float = Field(ge=0)
    quotes_count: int = Field(gt=0)


class BarsConfig(BaseModel):
    history_years: int = Field(gt=0)
    overlap_days: int = Field(ge=0)
    max_failure_ratio: float = Field(ge=0, le=1)


class PeaConfig(BaseModel):
    exclude: frozenset[str]


class Settings(StonksSettings):
    model_config = SettingsConfigDict(
        yaml_file=config_files("common/logging.yaml", "common/s3.yaml", "common/storage.yaml", "ingest.yaml"),
        env_prefix="INGEST_",
        env_nested_delimiter="__",
        extra="forbid",
    )

    http: HttpConfig
    universe: UniverseConfig
    yahoo: YahooConfig
    bars: BarsConfig
    pea: PeaConfig
