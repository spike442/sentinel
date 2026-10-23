from enum import StrEnum

from pydantic import BaseModel, Field


class DomainKind(StrEnum):
    WORKFLOW = "workflow"
    DATA = "data"


class Tone(StrEnum):
    ACTIVE = "active"
    WAITING = "waiting"
    DONE = "done"
    FAILED = "failed"
    CLOSED = "closed"


OPEN_TONES = frozenset({Tone.ACTIVE, Tone.WAITING})


class WorkflowSummary(BaseModel):
    id: str
    label: str
    agent: str
    running: bool
    active: int = 0


class DomainManifest(BaseModel):
    id: str
    label: str
    icon: str
    kind: DomainKind
    version: str
    enabled: bool = True
    running: bool
    active: int = 0
    workflows: list[WorkflowSummary] = Field(default_factory=list)


class ActionPrompt(BaseModel):
    message: str
    required: bool = False


class RecordAction(BaseModel):
    name: str
    label: str
    tone: str = "default"
    prompt: ActionPrompt | None = None
    confirm: str | None = None


class RecordLink(BaseModel):
    domain: str
    workflow: str
    record_id: str
    label: str


class ActionRequest(BaseModel):
    prompt: str = ""
    action_index: int | None = Field(default=None, ge=0)


class WorkflowState(BaseModel):
    name: str
    tone: Tone


class WorkflowTransition(BaseModel):
    source: str | None
    event: str
    target: str


class WorkflowView(BaseModel):
    domain: str
    states: list[WorkflowState]
    transitions: list[WorkflowTransition]
    tones: dict[str, Tone]


class Accepted(BaseModel):
    status: str = "accepted"
    workflow_id: str
