from pydantic_settings import SettingsConfigDict
from sentinel.core.config.common import CommonSettings
from sentinel.core.config.settings import config_files
from sentinel.core.contracts.reviews import RepositoryConfig


class ApiSettings(CommonSettings):
    model_config = SettingsConfigDict(
        yaml_file=config_files(
            "common/logging.yaml",
            "common/agents.yaml",
            "common/repositories.yaml",
            "common/kafka.yaml",
            "common/database.yaml",
        ),
        env_prefix="SENTINEL_",
        env_nested_delimiter="__",
        extra="forbid",
    )

    repositories: list[RepositoryConfig]
