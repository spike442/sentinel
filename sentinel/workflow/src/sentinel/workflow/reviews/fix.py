import logging

import httpx
from pydantic import BaseModel
from sentinel.core.config.workflow import PrReviewSettings
from sentinel.core.contracts.executor import FixPushed
from sentinel.core.contracts.reviews import (
    FailedPrReview,
    ProposedPrFix,
    PrReviewRequest,
    PullRequest,
    RepositoryConfig,
    configured_repository,
)
from sentinel.core.domain import ReviewTrigger
from sentinel.core.github import GitHubReader
from sentinel.core.kafka.contracts import AgentReturn, ExecutorAction, ExecutorReturn, WorkflowRequest
from sentinel.core.knowledge import KnowledgeClient
from sentinel.workflow.messages import DomainMessages
from sentinel.workflow.reviews import fix_policy
from sentinel.workflow.reviews.repository import PrReviewRepository
from sentinel.workflow.reviews.review import agent_outcome, prepared_with_history, search_review_knowledge

logger = logging.getLogger(__name__)


class FixRequest(BaseModel):
    review_id: str
    prompt: str = ""


class FixContext(BaseModel):
    review_id: str


class Fix:
    def __init__(
        self,
        settings: PrReviewSettings,
        reviews: PrReviewRepository,
        knowledge: KnowledgeClient,
        github: GitHubReader,
        messages: DomainMessages,
    ):
        self.repositories = settings.repositories
        self.reviews = reviews
        self.knowledge = knowledge
        self.github = github
        self.messages = messages

    def on_request(self, workflow_request: WorkflowRequest) -> None:
        request = FixRequest.model_validate(workflow_request.payload)
        review_id = request.review_id
        workflow_id = workflow_request.workflow_id
        review = self.reviews.get(review_id)
        if review is None:
            logger.warning("Fix for a deleted review review_id=%s", review_id)
            return
        repository = configured_repository(self.repositories, review["repository"], review["owner"])
        if repository is None:
            self.reviews.decline_fix(review_id, "The review repository is no longer configured.")
            return
        current = self.reviewed_revision(review_id, review, repository)
        if current is None:
            return
        claimed = self.reviews.claim_fix(review_id, workflow_id, request.prompt)
        if not claimed:
            return
        fix_request = PrReviewRequest(
            pull_request=current, repository=repository, trigger=ReviewTrigger.FIX, prompt=request.prompt
        )
        claimed_review = self.reviews.get(review_id)
        rag_context = search_review_knowledge(self.knowledge, current)
        prepared = prepared_with_history(fix_request, claimed_review, rag_context)
        self.messages.command_agent(workflow_id, prepared)

    def reviewed_revision(self, review_id: str, review: dict, repository: RepositoryConfig) -> PullRequest | None:
        try:
            state = self.github.pull_request_state(repository, review["pull_request_number"], review["head_sha"])
        except httpx.HTTPError as exc:
            error_type = type(exc).__name__
            self.reviews.decline_fix(review_id, f"GitHub lookup failed: {error_type}.")
            return None
        if state.merged_sha:
            self.reviews.mark_merged(review_id, state.merged_sha)
            return None
        current = state.pull_request
        if current is None:
            self.reviews.decline_fix(review_id, "The pull request is closed.")
            return None
        if (current.base_sha, current.head_sha) != (review["base_sha"], review["head_sha"]):
            self.reviews.decline_fix(
                review_id, "The PR changed since its review; Check now reviews its latest revision."
            )
            return None
        if current.head_repository != repository.full_name:
            self.reviews.decline_fix(review_id, "The PR branch is in a fork Sentinel cannot push to.")
            return None
        return current

    def on_agent_return(self, agent_return: AgentReturn, request: PrReviewRequest) -> None:
        review_id = PrReviewRepository.id_for(request.pull_request)
        workflow_id = agent_return.workflow_id
        outcome = agent_outcome(agent_return)
        if isinstance(outcome, ProposedPrFix):
            reason = fix_policy.rejection(outcome)
            if reason is None:
                self.push_fix(review_id, outcome, request.repository, workflow_id)
                return
            self.reviews.decline_fix(review_id, reason, workflow_id, outcome)
        elif isinstance(outcome, FailedPrReview):
            self.reviews.fail_review(
                review_id, workflow_id, outcome.failure, outcome.audit_actions, outcome.tool_budget
            )
        else:
            self.reviews.fail_review(review_id, workflow_id, agent_return.error or "AgentFailed")
        self.messages.announce_outcome(review_id, workflow_id)

    def push_fix(self, review_id: str, proposal: ProposedPrFix, repository: RepositoryConfig, workflow_id: str) -> None:
        saved = self.reviews.save_fix(review_id, workflow_id, proposal)
        if not saved:
            return
        push = fix_policy.push_request(proposal, repository)
        context = FixContext(review_id=review_id)
        self.messages.command_executor(ExecutorAction.PUSH_FIX, workflow_id, push, context)

    def on_executor_return(self, executor_return: ExecutorReturn) -> None:
        review_id = FixContext.model_validate(executor_return.context).review_id
        workflow_id = executor_return.workflow_id
        if executor_return.result is None:
            error = f"Pushing the fix failed: {executor_return.error or 'ExecutorFailed'}"
            self.reviews.fail_review(review_id, workflow_id, error)
        else:
            pushed = FixPushed.model_validate(executor_return.result)
            self.reviews.mark_fix_pushed(review_id, workflow_id, pushed.sha)
        self.messages.announce_outcome(review_id, workflow_id)
