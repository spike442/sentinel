from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict
from sentinel.agents.framework.runner import AgentConfig
from sentinel.agents.sre.incident.settings import PrometheusConfig, ShellConfig
from sentinel.core.config.settings import AgentSettings, config_files


class LimitsConfig(BaseModel):
    max_tool_calls: int = Field(gt=0)
    max_tool_output_bytes: int = Field(gt=0)
    run_timeout_seconds: int = Field(gt=0)


class Settings(AgentSettings):
    model_config = SettingsConfigDict(
        yaml_file=config_files(
            "common/logging.yaml",
            "common/s3.yaml",
            "common/llm.yaml",
            "common/kafka.yaml",
            "common/knowledge-api.yaml",
            "sre.yaml",
        ),
        env_prefix="SRE_",
        env_nested_delimiter="__",
        extra="forbid",
    )

    shell: ShellConfig
    prometheus: PrometheusConfig
    limits: LimitsConfig

    @property
    def agent(self) -> AgentConfig:
        return AgentConfig(llm=self.llm, max_tool_calls=self.limits.max_tool_calls)
