from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import SettingsConfigDict
from sentinel.core.config.settings import KafkaClientSettings, LoggingConfig, config_files


class CommandLimits(BaseModel):
    max_output_bytes: int = Field(gt=0)


class ExecutorConfig(BaseModel):
    commands: CommandLimits
    action_timeout_seconds: int = Field(gt=0)


class ExecutorSettings(KafkaClientSettings):
    model_config = SettingsConfigDict(
        yaml_file=config_files("common/logging.yaml", "common/kafka.yaml", "executor.yaml"),
        env_prefix="SENTINEL_",
        env_nested_delimiter="__",
        extra="forbid",
    )

    logging: LoggingConfig
    executor: ExecutorConfig
    github_app_id: str = Field(min_length=1, validation_alias="SENTINEL_GITHUB_APP_ID")
    github_installation_id: str = Field(min_length=1, validation_alias="SENTINEL_GITHUB_INSTALLATION_ID")
    github_private_key: SecretStr = Field(min_length=1, validation_alias="SENTINEL_GITHUB_APP_PRIVATE_KEY")
