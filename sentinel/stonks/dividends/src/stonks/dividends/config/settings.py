from datetime import date

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import SettingsConfigDict
from sentinel.agents.dividends.settings import ExcerptConfig
from sentinel.agents.framework.runner import AgentConfig
from sentinel.core.config.settings import LLMConfig
from stonks.core.settings import HttpConfig, StonksSettings, config_files


class SearchConfig(BaseModel):
    url: str
    max_results: int = Field(gt=0)


class PagesConfig(ExcerptConfig):
    max_bytes: int = Field(gt=0)


class LimitsConfig(BaseModel):
    max_tool_calls: int = Field(gt=0)
    run_timeout_seconds: int = Field(gt=0)


class ResearchConfig(BaseModel):
    max_instruments: int = Field(gt=0)
    recheck_days: int = Field(gt=0)
    max_failure_ratio: float = Field(ge=0, le=1)


class ValidationConfig(BaseModel):
    newswire_domains: frozenset[str] = Field(min_length=1)
    issuer_domains: dict[str, str]
    name_stopwords: frozenset[str]
    month_names: dict[int, list[str]] = Field(min_length=12, max_length=12)
    same_day_record_from: date
    calendar_days_ahead: int = Field(gt=0)


class Settings(StonksSettings):
    model_config = SettingsConfigDict(
        yaml_file=config_files(
            "common/logging.yaml", "common/s3.yaml", "common/storage.yaml", "common/llm.yaml", "dividends.yaml"
        ),
        env_prefix="DIVIDENDS_",
        env_nested_delimiter="__",
        extra="forbid",
    )

    http: HttpConfig
    llm: LLMConfig
    search: SearchConfig
    pages: PagesConfig
    limits: LimitsConfig
    research: ResearchConfig
    validation: ValidationConfig
    llm_api_key: SecretStr = Field(min_length=1, validation_alias="LLM_API_KEY")

    @property
    def agent(self) -> AgentConfig:
        return AgentConfig(llm=self.llm, max_tool_calls=self.limits.max_tool_calls)
