import json

from pydantic import TypeAdapter
from sentinel.core.config.workflow import PrReviewSettings
from sentinel.core.contracts.history import prior_attempts
from sentinel.core.contracts.knowledge import KnowledgeSearchRequest, RetrievedContext
from sentinel.core.contracts.reviews import (
    DecidedPrReview,
    PreparedPrReview,
    PrReviewOutcome,
    PrReviewRequest,
    PullRequest,
)
from sentinel.core.domain import AgentDomain
from sentinel.core.kafka.contracts import AgentReturn, WorkflowRequest
from sentinel.core.knowledge import KnowledgeClient
from sentinel.workflow.messages import DomainMessages
from sentinel.workflow.sre.reviews.merge import Merge
from sentinel.workflow.sre.reviews.repository import PrReviewRepository

review_result = TypeAdapter(PrReviewOutcome)


def agent_outcome(agent_return: AgentReturn) -> PrReviewOutcome:
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
        self.reviews = reviews
        self.knowledge = knowledge
        self.messages = messages
        self.merge = merge

    def on_request(self, workflow_request: WorkflowRequest) -> None:
        request = PrReviewRequest.model_validate(workflow_request.payload)
        workflow_id = workflow_request.workflow_id
        prepared = self.prepare_review(request, workflow_id)
        if prepared is not None:
            review_id = PrReviewRepository.id_for(request.pull_request)
            self.messages.command_agent(review_id, workflow_id, prepared)

    def prepare_review(self, request: PrReviewRequest, workflow_id: str) -> PreparedPrReview | None:
        pull_request = request.pull_request
        review_id = PrReviewRepository.id_for(pull_request)
        claimed = self.reviews.claim_review(review_id, request, workflow_id)
        if not claimed:
            return None
        if not pull_request.mergeable:
            self.messages.fail(review_id, workflow_id, "GitHub does not report the PR mergeable and clean")
            return None
        review = self.reviews.get(review_id)
        rag_context = search_review_knowledge(self.knowledge, pull_request)
        return prepared_with_history(request, review, rag_context)

    def on_agent_return(self, agent_return: AgentReturn) -> None:
        review_id = agent_return.record_id
        workflow_id = agent_return.workflow_id
        if agent_return.failure is not None:
            self.messages.fail(review_id, workflow_id, agent_return.failure)
            return
        outcome = agent_outcome(agent_return)
        if not isinstance(outcome, DecidedPrReview):
            self.messages.fail(review_id, workflow_id, "UnexpectedAgentResult")
            return
        saved = self.reviews.save_review(review_id, outcome, workflow_id)
        if saved and outcome.decision.merge:
            self.merge.start_merge(review_id, outcome.pull_request, workflow_id)
