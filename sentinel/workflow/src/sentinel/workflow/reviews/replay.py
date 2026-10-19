import logging

import httpx
from pydantic import BaseModel
from sentinel.core.config.workflow import PrReviewSettings
from sentinel.core.contracts.reviews import PrReviewRequest, configured_repository
from sentinel.core.domain import ReviewTrigger
from sentinel.core.github import GitHubReader
from sentinel.core.kafka.contracts import RequestKind, WorkflowRequest
from sentinel.workflow.messages import DomainMessages
from sentinel.workflow.reviews.repository import PrReviewRepository

logger = logging.getLogger(__name__)


class ReplayRequest(BaseModel):
    review_id: str
    prompt: str = ""


class Replay:
    def __init__(
        self, settings: PrReviewSettings, reviews: PrReviewRepository, github: GitHubReader, messages: DomainMessages
    ):
        self.repositories = settings.repositories
        self.reviews = reviews
        self.github = github
        self.messages = messages

    def on_request(self, workflow_request: WorkflowRequest) -> None:
        request = ReplayRequest.model_validate(workflow_request.payload)
        review_id = request.review_id
        review = self.reviews.get(review_id)
        if review is None:
            logger.warning("Replay for a deleted review review_id=%s", review_id)
            return
        repository = configured_repository(self.repositories, review["repository"], review["owner"])
        if repository is None:
            self.reviews.reject_replay(review_id, "The review repository is no longer configured.")
            return
        try:
            state = self.github.pull_request_state(repository, review["pull_request_number"], review["head_sha"])
        except httpx.HTTPError as exc:
            error_type = type(exc).__name__
            self.reviews.reject_replay(review_id, f"GitHub lookup failed: {error_type}.")
            return
        if state.merged_sha:
            self.reviews.mark_merged(review_id, state.merged_sha)
            return
        current = state.pull_request
        if current is None:
            self.reviews.reject_replay(review_id, "The pull request is closed.")
            return
        replayed = PrReviewRequest(
            pull_request=current, repository=repository, trigger=ReviewTrigger.REPLAY, prompt=request.prompt
        )
        self.messages.schedule(RequestKind.PR_REVIEW, workflow_request.workflow_id, replayed)
