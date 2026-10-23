import os
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, YamlConfigSettingsSource


def config_files(*names: str) -> list[Path]:
    directory = Path(os.environ.get("STONKS_CONFIG_DIR", "/etc/stonks"))
    return [directory / Path(name).name for name in names]


class LoggingConfig(BaseModel):
    level: str


class S3Config(BaseModel):
    endpoint: str
    region: str
    bucket: str


class StorageConfig(BaseModel):
    raw_prefix: str
    universe_prefix: str
    reference_prefix: str


class HttpConfig(BaseModel):
    timeout_seconds: float = Field(gt=0)
    user_agent: str = Field(min_length=1)
    max_retries: int = Field(ge=0)
    retry_backoff_seconds: float = Field(ge=0)


class StonksSettings(BaseSettings):
    logging: LoggingConfig
    s3: S3Config
    storage: StorageConfig
    s3_access_key_id: SecretStr = Field(min_length=1, validation_alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: SecretStr = Field(min_length=1, validation_alias="S3_SECRET_ACCESS_KEY")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls, deep_merge=True),
            file_secret_settings,
        )
