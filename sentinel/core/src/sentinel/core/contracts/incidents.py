from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sentinel.core.contracts.changes import ProposedChange
from sentinel.core.contracts.history import PriorAttempt
from sentinel.core.contracts.knowledge import RetrievedContext
from sentinel.core.contracts.reviews import RepositoryConfig
from sentinel.core.domain import (
    ActionStatus,
    AlertStatus,
    ConfidenceLevel,
    DiagnosisStatus,
    IncidentStatus,
    RiskLevel,
)
from sentinel.core.observability.audit import AuditAction, ToolBudget


class Alert(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: AlertStatus
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: str = ""
    endsAt: str = ""
    fingerprint: str = Field(min_length=1)

    @property
    def source(self) -> str:
        return self.labels.get("source", "")


class AlertmanagerNotification(BaseModel):
    alerts: list[Alert]


class ManualAction(BaseModel):
    title: str
    command: str
    reason: str
    validation: str


class Diagnosis(BaseModel):
    status: DiagnosisStatus = DiagnosisStatus.BLOCKED
    incident: str = "unknown incident"
    hypothesis: str = "Insufficient evidence to determine the root cause."
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    evidence: list[str] = Field(default_factory=list)
    proposed_files: list[str] = Field(default_factory=list)
    risk: RiskLevel = RiskLevel.LOW
    validation: list[str] = Field(default_factory=list)
    rollback: str = ""
    pr_title: str = ""
    pr_body: str = ""
    proposed_changes: list[ProposedChange] = Field(default_factory=list)
    manual_actions: list[ManualAction] = Field(default_factory=list)

    @property
    def proposes_fix(self) -> bool:
        return self.status is DiagnosisStatus.PROPOSED and bool(self.proposed_changes)


class IncidentRequest(BaseModel):
    kind: Literal["alert", "replay"]
    incident_id: str = Field(min_length=1)
    alert: Alert | None = None
    prompt: str = ""

    @model_validator(mode="after")
    def alert_runs_carry_their_alert(self) -> "IncidentRequest":
        if self.kind == "alert" and self.alert is None:
            raise ValueError("an alert run requires its alert")
        return self


class PreparedIncident(IncidentRequest):
    alert: Alert
    repository: RepositoryConfig
    rag_context: list[RetrievedContext]
    history: list[PriorAttempt] = Field(default_factory=list, description="Earlier attempts a replay builds on.")


class IncidentResult(BaseModel):
    status: IncidentStatus
    diagnosis: Diagnosis
    audit_actions: list[AuditAction] = Field(default_factory=list, description="This run's actions only.")
    tool_budget: ToolBudget = Field(default_factory=ToolBudget)
    pull_request_url: str | None = None


class ManualActionRequest(BaseModel):
    incident_id: str
    action_index: int = Field(ge=0)
    approval_id: str
    action: ManualAction


class ClaimedAction(ManualActionRequest):
    claim_at: str


class ActionOutput(BaseModel):
    status: ActionStatus
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    reason: str | None = None
