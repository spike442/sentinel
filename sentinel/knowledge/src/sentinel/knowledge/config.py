from pathlib import Path

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import SettingsConfigDict
from sentinel.core.config.settings import (
    DatabaseConfig,
    LoggingConfig,
    S3ServiceConfig,
    YamlSettings,
    config_files,
    postgres_dsn,
)
from sentinel.core.domain import AgentDomain


class ClickHouseConfig(BaseModel):
    host: str
    port: int
    database: str
    user: str


class RagSourceConfig(BaseModel):
    domains: list[AgentDomain]
    repository: str


class RagConfig(BaseModel):
    embedding_model: str
    embedding_model_path: Path
    embedding_revision: str
    document_prefix: str
    query_prefix: str
    chunk_tokens: int = Field(gt=0)
    overlap_tokens: int = Field(ge=0)
    batch_size: int = Field(gt=0)
    candidate_results: int = Field(gt=0)
    max_context_tokens: int = Field(gt=0)
    max_results: int = Field(gt=0)
    index_interval_seconds: int = Field(gt=0)
    sources: list[RagSourceConfig]


class KnowledgeSettings(YamlSettings):
    model_config = SettingsConfigDict(
        yaml_file=config_files(
            "common/logging.yaml", "knowledge.yaml", "common/database.yaml", "common/clickhouse.yaml", "common/s3.yaml"
        ),
        env_prefix="SENTINEL_",
        env_nested_delimiter="__",
        extra="forbid",
    )

    logging: LoggingConfig
    rag: RagConfig
    clickhouse: ClickHouseConfig
    s3: S3ServiceConfig
    clickhouse_password: SecretStr = Field(min_length=1, validation_alias="SENTINEL_CLICKHOUSE_PASSWORD")
    database: DatabaseConfig
    knowledge_database_user: str
    knowledge_database_password: SecretStr = Field(
        min_length=1, validation_alias="SENTINEL_KNOWLEDGE_DATABASE_PASSWORD"
    )
    s3_access_key_id: str = Field(min_length=1, validation_alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: SecretStr = Field(min_length=1, validation_alias="S3_SECRET_ACCESS_KEY")

    @property
    def database_dsn(self) -> str:
        password = self.knowledge_database_password.get_secret_value()
        return postgres_dsn(self.database, self.knowledge_database_user, password)
