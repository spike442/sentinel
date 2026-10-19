import json
from datetime import datetime, timedelta

from pydantic import TypeAdapter
from sentinel.core.config.workflow import PrReviewSettings
from sentinel.core.contracts.history import prior_attempts
from sentinel.core.contracts.knowledge import KnowledgeSearchRequest, RetrievedContext
from sentinel.core.contracts.reviews import (
    DecidedPrReview,
    FailedPrReview,
    PreparedPrReview,
    PrReviewOutcome,
    PrReviewRequest,
    PullRequest,
)
from sentinel.core.domain import AgentDomain
from sentinel.core.kafka.contracts import AgentReturn, WorkflowRequest
from sentinel.core.knowledge import KnowledgeClient
from sentinel.core.state import review_rules as rules
from sentinel.workflow.messages import DomainMessages
from sentinel.workflow.reviews.merge import Merge
from sentinel.workflow.reviews.repository import PrReviewRepository

review_result = TypeAdapter(PrReviewOutcome)


def agent_outcome(agent_return: AgentReturn) -> PrReviewOutcome | None:
    if agent_return.result is None:
        return None
    return review_result.validate_python(agent_return.result)


def search_review_knowledge(knowledge: KnowledgeClient, pull_request: PullRequest) -> list[RetrievedContext]:
    pull_request_fields = pull_request.model_dump(mode="json")
    query = json.dumps(pull_request_fields, sort_keys=True)
    search = KnowledgeSearchRequest(
        domain=AgentDomain.PULL_REQUEST_REVIEW, repository=pull_request.repository, query=query
    )
    return knowledge.search(search)


def prepared_with_history(
    request: PrReviewRequest, review: dict, rag_context: list[RetrievedContext]
) -> PreparedPrReview:
    history = prior_attempts(review["attempts"])
    request_fields = request.model_dump()
    return PreparedPrReview(**request_fields, rag_context=rag_context, history=history)


class PrReviewRun:
    def __init__(
        self,
        settings: PrReviewSettings,
        reviews: PrReviewRepository,
        knowledge: KnowledgeClient,
        messages: DomainMessages,
        merge: Merge,
    ):
        self.workflow_timeout = timedelta(seconds=settings.workflow_timeout_seconds)
        self.reviews = reviews
        self.knowledge = knowledge
        self.messages = messages
        self.merge = merge

    def on_request(self, workflow_request: WorkflowRequest) -> None:
        request = PrReviewRequest.model_validate(workflow_request.payload)
        workflow_id = workflow_request.workflow_id
        prepared = self.prepare_review(request, workflow_id)
        if prepared is not None:
            self.messages.command_agent(workflow_id, prepared)

    def prepare_review(self, request: PrReviewRequest, workflow_id: str) -> PreparedPrReview | None:
        pull_request = request.pull_request
        review_id = PrReviewRepository.id_for(pull_request)
        claimed = self.reviews.claim_review(review_id, request, workflow_id)
        if not claimed:
            return None
        if not pull_request.mergeable:
            self.reviews.fail_review(review_id, workflow_id, "GitHub does not report the PR mergeable and clean")
            self.messages.announce_outcome(review_id, workflow_id)
            return None
        review = self.reviews.get(review_id)
        rag_context = search_review_knowledge(self.knowledge, pull_request)
        return prepared_with_history(request, review, rag_context)

    def on_agent_return(self, agent_return: AgentReturn, request: PrReviewRequest) -> None:
        review_id = PrReviewRepository.id_for(request.pull_request)
        workflow_id = agent_return.workflow_id
        outcome = agent_outcome(agent_return)
        if isinstance(outcome, DecidedPrReview):
            saved = self.reviews.save_review(review_id, outcome, workflow_id)
            if saved and outcome.decision.merge:
                self.merge.start_merge(review_id, outcome.pull_request, workflow_id)
        elif isinstance(outcome, FailedPrReview):
            self.reviews.fail_review(
                review_id, workflow_id, outcome.failure, outcome.audit_actions, outcome.tool_budget
            )
        else:
            self.reviews.fail_review(review_id, workflow_id, agent_return.error or "AgentFailed")
        self.messages.announce_outcome(review_id, workflow_id)

    def expire_reviews(self, now: datetime) -> None:
        for status in sorted(rules.ACTIVE):
            reviews = self.reviews.list(500, status=status, oldest_first=True)
            for review in reviews:
                updated_at = datetime.fromisoformat(review["updated_at"])
                timed_out = rules.workflow_timed_out(review["status"], updated_at, now, self.workflow_timeout)
                if timed_out:
                    self.reviews.fail_review(review["id"], review["workflow_id"], "AgentTimedOut")
                    self.messages.announce_outcome(review["id"], review["workflow_id"])
