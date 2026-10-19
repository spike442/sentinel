from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sentinel.core.domain import AuditStatus


class AuditAction(BaseModel):
    action: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime


class ToolBudget(BaseModel):
    limit: int = 0
    calls: dict[str, int] = Field(default_factory=dict)
    exhausted_tools: list[str] = Field(default_factory=list)

    @property
    def exhausted(self) -> bool:
        return bool(self.exhausted_tools)


class AuditLog:
    def __init__(self) -> None:
        self.actions: list[AuditAction] = []
        self.tool_budget = ToolBudget()

    def record(self, action: str, details: dict[str, Any]) -> None:
        timestamp = datetime.now(UTC)
        entry = AuditAction(action=action, details=details, timestamp=timestamp)
        self.actions.append(entry)

    def record_model_response(self, response_id: str | None, usage: dict[str, Any] | None = None) -> None:
        details: dict[str, Any] = {"status": AuditStatus.COMPLETED.value}
        if response_id:
            details["response_id"] = response_id
        if usage:
            details["usage"] = usage
        self.record("llm_response", details)

    def record_tool_budget(self, budget: ToolBudget) -> None:
        self.tool_budget = budget
        if budget.exhausted:
            details = budget.model_dump(mode="json")
            self.record("tool_budget_exhausted", details)

    def record_model_failure(self, error: Exception) -> None:
        details = {"status": AuditStatus.FAILED.value, "error": type(error).__name__}
        self.record("llm_response", details)
