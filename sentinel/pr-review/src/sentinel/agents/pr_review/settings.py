from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict
from sentinel.core.config.settings import AgentSettings, config_files
from sentinel.core.domain import ConfidenceLevel, RiskLevel


class PrReviewConfig(BaseModel):
    allowed_risk_levels: set[RiskLevel]
    allowed_confidence_levels: set[ConfidenceLevel]
    max_diff_bytes: int = Field(gt=0)
    max_file_bytes: int = Field(gt=0)
    max_tool_calls: int = Field(gt=0)
    max_command_output_bytes: int = Field(gt=0)
    run_timeout_seconds: int = Field(gt=0)


class Settings(AgentSettings):
    model_config = SettingsConfigDict(
        yaml_file=config_files(
            "common/logging.yaml",
            "common/s3.yaml",
            "common/llm.yaml",
            "common/kafka.yaml",
            "common/knowledge-api.yaml",
            "pr-review.yaml",
        ),
        env_prefix="PR_REVIEW_",
        env_nested_delimiter="__",
        extra="forbid",
    )

    review: PrReviewConfig
