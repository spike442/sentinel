from pydantic_settings import SettingsConfigDict
from stonks.core.settings import StonksSettings, config_files


class Settings(StonksSettings):
    model_config = SettingsConfigDict(
        yaml_file=config_files("common/logging.yaml", "common/s3.yaml", "common/storage.yaml"),
        env_prefix="API_",
        env_nested_delimiter="__",
        extra="forbid",
    )
