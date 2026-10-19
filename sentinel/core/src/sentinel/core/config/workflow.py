from typing import Any

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import SettingsConfigDict
from sentinel.core.config.common import CommonSettings
from sentinel.core.config.settings import KnowledgeConfig, LoggingConfig, YamlSettings, config_files
from sentinel.core.contracts.reviews import RepositoryConfig, configured_repository
from sentinel.core.domain import AgentDomain

DOMAIN_SECTIONS = ("sre", "pr_review")


def domain_settings(values: dict[str, Any], domain: str) -> dict[str, Any]:
    shared = {key: value for key, value in values.items() if key not in DOMAIN_SECTIONS}
    return {**shared, **values[domain]}


class IncidentConfig(BaseModel):
    repository: str
    branch_prefix: str
    manual_action_timeout_seconds: int = Field(gt=0)
    workflow_timeout_seconds: int = Field(gt=0)


class AlertmanagerConfig(BaseModel):
    url: str


class WorkflowAgents(YamlSettings):
    model_config = SettingsConfigDict(
        yaml_file=config_files("common/logging.yaml", "common/agents.yaml"),
        env_prefix="SENTINEL_",
        extra="forbid",
    )

    agents: list[AgentDomain]
    logging: LoggingConfig


class WorkflowSettings(CommonSettings):
    model_config = SettingsConfigDict(
        yaml_file=config_files(
            "common/logging.yaml",
            "common/agents.yaml",
            "common/repositories.yaml",
            "common/kafka.yaml",
            "common/knowledge-api.yaml",
            "workflow.yaml",
            "common/database.yaml",
        ),
        env_prefix="SENTINEL_",
        env_nested_delimiter="__",
        extra="forbid",
    )

    knowledge: KnowledgeConfig
    repositories: list[RepositoryConfig]
    discord_webhook_url: SecretStr = Field(min_length=1, validation_alias="SENTINEL_DISCORD_WEBHOOK_URL")


class PrReviewSettings(WorkflowSettings):
    review_poll_seconds: int = Field(gt=0)
    merge_method: str
    workflow_timeout_seconds: int = Field(gt=0)
    github_app_id: str = Field(min_length=1, validation_alias="SENTINEL_GITHUB_APP_ID")
    github_installation_id: str = Field(min_length=1, validation_alias="SENTINEL_GITHUB_INSTALLATION_ID")
    github_private_key: SecretStr = Field(min_length=1, validation_alias="SENTINEL_GITHUB_APP_PRIVATE_KEY")

    @model_validator(mode="before")
    @classmethod
    def select_domain(cls, values: dict[str, Any]) -> dict[str, Any]:
        return domain_settings(values, "pr_review")


class IncidentSettings(WorkflowSettings):
    incident: IncidentConfig
    alertmanager: AlertmanagerConfig

    @model_validator(mode="before")
    @classmethod
    def select_domain(cls, values: dict[str, Any]) -> dict[str, Any]:
        return domain_settings(values, "sre")

    @model_validator(mode="after")
    def incident_repository_is_configured(self) -> "IncidentSettings":
        if configured_repository(self.repositories, self.incident.repository) is None:
            raise ValueError(f"incident repository is not configured: {self.incident.repository}")
        return self

    @property
    def incident_repository(self) -> RepositoryConfig:
        return configured_repository(self.repositories, self.incident.repository)
