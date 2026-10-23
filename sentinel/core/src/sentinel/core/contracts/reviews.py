from typing import Annotated, Literal

from pydantic import BaseModel, Field
from sentinel.core.contracts.changes import ProposedChange
from sentinel.core.contracts.history import PriorAttempt
from sentinel.core.contracts.knowledge import RetrievedContext
from sentinel.core.domain import ConfidenceLevel, RepositoryIdentity, ReviewTrigger, RiskLevel
from sentinel.core.observability.audit import AuditAction, ToolBudget


class PullRequest(BaseModel):
    owner: str
    repository: str
    number: int
    base_sha: str
    head_sha: str
    html_url: str = ""
    updated_at: str = ""
    title: str = ""
    author: str = ""
    head_ref: str = ""
    head_repository: str = Field(default="", description="``owner/name`` of the head branch; a fork differs.")
    labels: list[str] = Field(default_factory=list)
    mergeable: bool = False


class RepositoryConfig(RepositoryIdentity):
    branch: str
    clone_depth: int = Field(gt=0)


def configured_repository(
    repositories: list[RepositoryConfig], name: str, owner: str | None = None
) -> RepositoryConfig | None:
    for repository in repositories:
        if repository.name == name and owner in (None, repository.owner):
            return repository
    return None


class PullRequestState(BaseModel):
    merged_sha: str | None = Field(default=None, description="Set when exactly the reviewed head was merged.")
    pull_request: PullRequest | None = Field(default=None, description="The current revision while it is open.")


class PrReviewRequest(BaseModel):
    pull_request: PullRequest
    repository: RepositoryConfig
    trigger: ReviewTrigger = ReviewTrigger.REVIEW
    prompt: str = Field(default="", description="The operator's instruction for a replay or a fix.")


class PreparedPrReview(PrReviewRequest):
    rag_context: list[RetrievedContext]
    history: list[PriorAttempt] = Field(default_factory=list, description="Earlier attempts on this pull request.")


class CheckResult(BaseModel):
    name: str
    passed: bool
    output: str = ""


class PrReviewResult(BaseModel):
    risk: RiskLevel
    confidence: ConfidenceLevel
    summary: str
    findings: list[str] = Field(default_factory=list)


class PrReviewDecision(BaseModel):
    merge: bool
    reason: str


class DecidedPrReview(BaseModel):
    status: Literal["decided"] = "decided"
    pull_request: PullRequest
    checks: list[CheckResult]
    review: PrReviewResult
    decision: PrReviewDecision
    audit_actions: list[AuditAction] = Field(default_factory=list)
    tool_budget: ToolBudget = Field(default_factory=ToolBudget)


class FailedPrReview(BaseModel):
    status: Literal["failed"] = "failed"
    pull_request: PullRequest
    failure: str
    audit_actions: list[AuditAction] = Field(default_factory=list)
    tool_budget: ToolBudget = Field(default_factory=ToolBudget)


class PrFix(BaseModel):
    """The reviewer's fix of its own blocked review: complete new contents of each changed file, or its deletion."""

    summary: str = Field(description="What the fix changes and which findings it addresses.")
    commit_message: str = Field(description="A one-line commit subject for the fix.")
    changes: list[ProposedChange] = Field(
        default_factory=list,
        description="Each changed file's complete new content or deletion; empty when it cannot be fixed.",
    )


class ProposedPrFix(BaseModel):
    status: Literal["fix"] = "fix"
    pull_request: PullRequest
    fix: PrFix
    checks: list[CheckResult]
    audit_actions: list[AuditAction] = Field(default_factory=list)
    tool_budget: ToolBudget = Field(default_factory=ToolBudget)


PrReviewOutcome = Annotated[DecidedPrReview | FailedPrReview | ProposedPrFix, Field(discriminator="status")]
