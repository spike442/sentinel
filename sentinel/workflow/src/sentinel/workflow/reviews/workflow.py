from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sentinel.core.config.workflow import PrReviewSettings
from sentinel.core.contracts.reviews import PrReviewRequest
from sentinel.core.domain import AgentDomain, ReviewTrigger
from sentinel.core.github import GitHubReader
from sentinel.core.kafka.contracts import (
    AgentReturn,
    ExecutorAction,
    ExecutorReturn,
    KafkaTopic,
    RequestKind,
    WorkflowRequest,
)
from sentinel.core.knowledge import KnowledgeClient
from sentinel.workflow.discord import DiscordWebhook
from sentinel.workflow.messages import DomainMessages
from sentinel.workflow.reviews.discovery import Discovery
from sentinel.workflow.reviews.fix import Fix, FixRequest
from sentinel.workflow.reviews.merge import Merge
from sentinel.workflow.reviews.replay import Replay
from sentinel.workflow.reviews.repository import PrReviewRepository
from sentinel.workflow.reviews.review import PrReviewRun
from sentinel.workflow.routing import DomainWorkflow


def review_notice(review: dict[str, Any]) -> str:
    target = f"{review['owner']}/{review['repository']}#{review['pull_request_number']}"
    lines = [f"**PR review {review['status']}** · {target}"]
    reason = review["decision_reason"] or review["summary"]
    if reason:
        lines.append(reason)
    lines.append(review["pull_request_url"])
    return "\n".join(lines)


class PrReviewWorkflow(DomainWorkflow):
    def __init__(
        self,
        settings: PrReviewSettings,
        reviews: PrReviewRepository,
        knowledge: KnowledgeClient,
        github: GitHubReader,
        discord: DiscordWebhook,
    ):
        messages = DomainMessages(
            settings,
            AgentDomain.PULL_REQUEST_REVIEW,
            KafkaTopic.PR_REVIEW_COMMANDS,
            RequestKind.PR_REVIEW,
            records=reviews,
            describe=review_notice,
            discord=discord,
        )
        reviews.on_terminal = messages.notify
        self.reviews = reviews
        self.messages = messages
        self.discovery = Discovery(settings, reviews, github, messages)
        self.merge = Merge(settings, reviews, messages)
        self.replay = Replay(settings, reviews, github, messages)
        self.fix = Fix(settings, reviews, knowledge, github, messages)
        self.review = PrReviewRun(settings, reviews, knowledge, messages, self.merge)
        super().__init__(
            AgentDomain.PULL_REQUEST_REVIEW,
            topics={KafkaTopic.PR_REVIEW_RETURNS: self._on_agent_return},
            requests={
                RequestKind.DISCOVER: self.discovery.on_request,
                RequestKind.PR_REVIEW: self.review.on_request,
                RequestKind.REPLAY: self.replay.on_request,
                RequestKind.FIX: self.fix.on_request,
                RequestKind.DELETE: self._on_delete,
            },
            executor_returns={
                ExecutorAction.MERGE_PULL_REQUEST: self.merge.on_executor_return,
                ExecutorAction.PUSH_FIX: self.fix.on_executor_return,
            },
        )

    def fail_record(self, topic: KafkaTopic, payload: dict[str, Any], error: str) -> None:
        if topic is KafkaTopic.PR_REVIEW_RETURNS:
            agent_return = AgentReturn.model_validate(payload)
            request = PrReviewRequest.model_validate(agent_return.request)
            review_id = PrReviewRepository.id_for(request.pull_request)
            workflow_id = agent_return.workflow_id
        elif topic is KafkaTopic.WORKFLOW_REQUESTS:
            workflow_request = WorkflowRequest.model_validate(payload)
            if workflow_request.kind is RequestKind.PR_REVIEW:
                request = PrReviewRequest.model_validate(workflow_request.payload)
                review_id = PrReviewRepository.id_for(request.pull_request)
            elif workflow_request.kind is RequestKind.FIX:
                review_id = FixRequest.model_validate(workflow_request.payload).review_id
            else:
                return
            workflow_id = workflow_request.workflow_id
        elif topic is KafkaTopic.EXECUTOR_RETURNS:
            executor_return = ExecutorReturn.model_validate(payload)
            review_id = executor_return.context.get("review_id")
            if review_id is None:
                return
            workflow_id = executor_return.workflow_id
        else:
            return
        self.reviews.fail_review(review_id, workflow_id, error)
        self.messages.announce_outcome(review_id, workflow_id)

    def expire_workflows(self) -> None:
        now = datetime.now(UTC)
        self.review.expire_reviews(now)

    def schedule_discovery(self) -> None:
        workflow_id = f"pr-review-poll-{uuid4()}"
        self.messages.schedule(RequestKind.DISCOVER, workflow_id)

    def _on_agent_return(self, payload: dict[str, Any]) -> None:
        agent_return = AgentReturn.model_validate(payload)
        request = PrReviewRequest.model_validate(agent_return.request)
        if request.trigger is ReviewTrigger.FIX:
            self.fix.on_agent_return(agent_return, request)
        else:
            self.review.on_agent_return(agent_return, request)

    def _on_delete(self, request: WorkflowRequest) -> None:
        self.reviews.delete_review(request.payload["review_id"])
