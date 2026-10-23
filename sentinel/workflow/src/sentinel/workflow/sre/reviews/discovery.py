import logging
from uuid import uuid4

import httpx
from sentinel.core.config.workflow import PrReviewSettings
from sentinel.core.contracts.reviews import PrReviewRequest, configured_repository
from sentinel.core.github import GitHubReader
from sentinel.core.kafka.contracts import RequestKind, WorkflowRequest
from sentinel.workflow.messages import DomainMessages
from sentinel.workflow.sre.reviews.incident_link import IncidentLink
from sentinel.workflow.sre.reviews.repository import PrReviewRepository

logger = logging.getLogger(__name__)


class Discovery:
    def __init__(
        self,
        settings: PrReviewSettings,
        reviews: PrReviewRepository,
        github: GitHubReader,
        messages: DomainMessages,
        link: IncidentLink,
    ):
        self.repositories = settings.repositories
        self.reviews = reviews
        self.link = link
        self.github = github
        self.messages = messages

    def on_request(self, workflow_request: WorkflowRequest) -> None:
        """Acknowledge and schedule each open pull request GitHub reports clean whose current revision needs review.

        That is a new pull request, an acknowledged one (including a pushed fix), or a blocked or failed one whose
        base or head changed. A pull request whose checks still run is skipped; a later poll finds it once clean.
        """
        try:
            pull_requests = self.github.reviewable_pull_requests(self.repositories)
        except httpx.HTTPError as exc:
            error_type = type(exc).__name__
            logger.error("PR discovery failed workflow_id=%s error=%s", workflow_request.workflow_id, error_type)
            return
        for pull_request in pull_requests:
            if not pull_request.mergeable:
                continue
            repository = configured_repository(self.repositories, pull_request.repository, pull_request.owner)
            if repository is None:
                continue
            unreviewed = self.reviews.needs_review(pull_request)
            if not unreviewed:
                continue
            review_id = PrReviewRepository.id_for(pull_request)
            self.link.acknowledge(review_id, pull_request)
            request = PrReviewRequest(pull_request=pull_request, repository=repository)
            review_workflow_id = f"pr-review-{uuid4()}"
            self.messages.schedule(RequestKind.PR_REVIEW, review_workflow_id, request, record_id=review_id)
