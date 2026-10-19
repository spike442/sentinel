from pydantic import Field, SecretStr
from sentinel.core.config.settings import DatabaseConfig, KafkaClientSettings, LoggingConfig, postgres_dsn
from sentinel.core.domain import AgentDomain


class CommonSettings(KafkaClientSettings):
    logging: LoggingConfig
    agents: list[AgentDomain]
    database: DatabaseConfig
    database_password: SecretStr = Field(min_length=1, validation_alias="SENTINEL_DATABASE_PASSWORD")

    @property
    def database_dsn(self) -> str:
        password = self.database_password.get_secret_value()
        return postgres_dsn(self.database, self.database.user, password)
