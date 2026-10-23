from datetime import timedelta
from typing import Any
from uuid import uuid4

from sentinel.core.config.workflow import PrReviewSettings
from sentinel.core.contracts.reviews import PrReviewRequest
from sentinel.core.domain import AgentDomain, ReviewTrigger
from sentinel.core.github import GitHubReader
from sentinel.core.kafka.contracts import AgentReturn, ExecutorAction, KafkaTopic, RequestKind
from sentinel.core.knowledge import KnowledgeClient
from sentinel.core.state import review_rules as rules
from sentinel.workflow.discord import DiscordWebhook
from sentinel.workflow.messages import DomainMessages
from sentinel.workflow.routing import DomainWorkflow
from sentinel.workflow.sre.reviews.discovery import Discovery
from sentinel.workflow.sre.reviews.fix import Fix
from sentinel.workflow.sre.reviews.incident_link import IncidentLink, IncidentRecords
from sentinel.workflow.sre.reviews.merge import Merge
from sentinel.workflow.sre.reviews.replay import Replay
from sentinel.workflow.sre.reviews.repository import PrReviewRepository
from sentinel.workflow.sre.reviews.review import PrReviewRun


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
        *,
        incidents: IncidentRecords,
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
        self.link = IncidentLink(reviews, incidents)
        reviews.on_terminal = self._on_terminal
        self.reviews = reviews
        self.discovery = Discovery(settings, reviews, github, messages, self.link)
        self.merge = Merge(settings, reviews, messages)
        self.replay = Replay(settings, reviews, github, messages)
        self.fix = Fix(settings, reviews, knowledge, github, messages)
        self.review = PrReviewRun(settings, reviews, knowledge, messages, self.merge)
        workflow_timeout = timedelta(seconds=settings.workflow_timeout_seconds)
        super().__init__(
            AgentDomain.PULL_REQUEST_REVIEW,
            reviews,
            messages,
            topics={KafkaTopic.PR_REVIEW_RETURNS: self._on_agent_return},
            requests={
                RequestKind.DISCOVER: self.discovery.on_request,
                RequestKind.PR_REVIEW: self.review.on_request,
                RequestKind.REPLAY: self.replay.on_request,
                RequestKind.FIX: self.fix.on_request,
            },
            executor_returns={
                ExecutorAction.MERGE_PULL_REQUEST: self.merge.on_executor_return,
                ExecutorAction.PUSH_FIX: self.fix.on_executor_return,
            },
            active=rules.ACTIVE,
            timed_out=rules.workflow_timed_out,
            workflow_timeout=workflow_timeout,
        )

    def _on_terminal(self, review_id: str) -> None:
        self.messages.notify(review_id)
        self.link.report(review_id)

    def schedule_discovery(self) -> None:
        workflow_id = f"pr-review-poll-{uuid4()}"
        self.messages.schedule(RequestKind.DISCOVER, workflow_id)

    def _on_agent_return(self, payload: dict[str, Any]) -> None:
        agent_return = AgentReturn.model_validate(payload)
        request = PrReviewRequest.model_validate(agent_return.request)
        if request.trigger is ReviewTrigger.FIX:
            self.fix.on_agent_return(agent_return, request)
        else:
            self.review.on_agent_return(agent_return)
