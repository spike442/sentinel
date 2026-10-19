import os
from pathlib import Path
from urllib.parse import quote

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, YamlConfigSettingsSource
from sentinel.core.kafka.contracts import KafkaTopic


def config_files(*names: str) -> list[Path]:
    directory = Path(os.environ.get("SENTINEL_CONFIG_DIR", "/etc/sentinel"))
    return [directory / Path(name).name for name in names]


class YamlSettings(BaseSettings):
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


class DatabaseConfig(BaseModel):
    host: str
    port: int
    name: str
    user: str


def postgres_dsn(database: DatabaseConfig, user: str, password: str) -> str:
    quoted_user = quote(user)
    quoted_password = quote(password)
    quoted_name = quote(database.name)
    return f"postgresql+psycopg://{quoted_user}:{quoted_password}@{database.host}:{database.port}/{quoted_name}"


class LoggingConfig(BaseModel):
    level: str


class LLMConfig(BaseModel):
    base_url: str
    model: str
    max_retries: int = Field(ge=0)
    request_timeout_seconds: int = Field(gt=0)


class KnowledgeConfig(BaseModel):
    endpoint: str


class S3ServiceConfig(BaseModel):
    endpoint: str
    region: str
    bucket: str


class KafkaConfig(BaseModel):
    bootstrap_servers: str
    security_protocol: str
    sasl_mechanisms: str
    consumer_group: str
    max_poll_interval_seconds: int = Field(gt=0)
    topics: dict[KafkaTopic, str]

    @field_validator("topics")
    @classmethod
    def every_topic_is_named(cls, topics: dict[KafkaTopic, str]) -> dict[KafkaTopic, str]:
        missing = sorted(topic.value for topic in KafkaTopic if not topics.get(topic))
        if missing:
            raise ValueError(f"Kafka topics need names: {', '.join(missing)}")
        return topics


class KafkaClientSettings(YamlSettings):
    kafka: KafkaConfig
    kafka_username: str = Field(min_length=1, validation_alias="SENTINEL_KAFKA_USERNAME")
    kafka_password: SecretStr = Field(min_length=1, validation_alias="SENTINEL_KAFKA_PASSWORD")


class AgentSettings(KafkaClientSettings):
    logging: LoggingConfig
    llm: LLMConfig
    knowledge: KnowledgeConfig
    s3: S3ServiceConfig
    s3_access_key_id: str = Field(min_length=1, validation_alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: SecretStr = Field(min_length=1, validation_alias="S3_SECRET_ACCESS_KEY")
    openai_api_key: SecretStr = Field(min_length=1, validation_alias="LLM_API_KEY")

    def known_secrets(self) -> tuple[str, ...]:
        return (
            self.openai_api_key.get_secret_value(),
            self.s3_secret_access_key.get_secret_value(),
            self.s3_access_key_id,
            self.kafka_password.get_secret_value(),
        )
