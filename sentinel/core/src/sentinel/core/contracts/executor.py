from enum import StrEnum

from pydantic import BaseModel, Field
from sentinel.core.contracts.changes import ProposedChange
from sentinel.core.contracts.reviews import PullRequest
from sentinel.core.domain import RepositoryIdentity


class CreatePullRequest(BaseModel):
    repository: RepositoryIdentity
    base_branch: str
    branch: str
    changes: list[ProposedChange] = Field(min_length=1)
    title: str
    body: str
    labels: list[str] = Field(default_factory=list)


class PullRequestCreated(BaseModel):
    url: str
    rejected: bool = Field(default=False, description="An identical fix was already closed without merging.")


class MergePullRequest(BaseModel):
    pull_request: PullRequest
    merge_method: str


class MergeStatus(StrEnum):
    MERGED = "merged"
    NOT_MERGEABLE = "not-mergeable"


class MergeOutcome(BaseModel):
    status: MergeStatus
    sha: str = ""


class PushFix(BaseModel):
    repository: RepositoryIdentity
    branch: str
    head_sha: str
    changes: list[ProposedChange] = Field(min_length=1)
    message: str


class FixPushed(BaseModel):
    sha: str


class RunCommand(BaseModel):
    command: str
    timeout_seconds: int = Field(gt=0)
