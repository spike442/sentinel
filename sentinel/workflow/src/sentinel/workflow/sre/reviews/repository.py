from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sentinel.core.contracts.reviews import DecidedPrReview, ProposedPrFix, PrReviewRequest, PullRequest
from sentinel.core.domain import PrReviewStatus
from sentinel.core.kafka.contracts import RunFailure
from sentinel.core.persistence.pr_review_record import PrReviewRecord
from sentinel.core.persistence.queries import PrReviewReader
from sentinel.core.state import review_rules as rules
from sentinel.core.state.outcomes import Accepted, require_allowed, require_existing, succeeded
from sentinel.workflow.repository import TransitionRepository, failure_trail
from sentinel.workflow.sre.reviews.events import (
    Acknowledged,
    Deleted,
    FixClaimed,
    FixDeclined,
    FixProposed,
    FixPushed,
    Merged,
    PrReviewClaimed,
    PrReviewFailed,
    ReplayRejected,
    ResultSaved,
)
from sentinel.workflow.sre.reviews.machine import transition
from sentinel.workflow.sre.reviews.snapshot import PrReview


class PrReviewRepository(TransitionRepository, PrReviewReader):
    state_type = PrReview
    decide = staticmethod(transition)
    terminal = rules.NOTIFIED

    @staticmethod
    def id_for(pull_request: PullRequest) -> str:
        key = f"{pull_request.owner}/{pull_request.repository}#{pull_request.number}"
        identity = uuid5(NAMESPACE_URL, key)
        return str(identity)

    def new_values(self, pull_request: PullRequest) -> dict[str, Any]:
        return {
            "workflow_id": None,
            "owner": pull_request.owner,
            "repository": pull_request.repository,
            "pull_request_number": pull_request.number,
            "base_sha": pull_request.base_sha,
            "head_sha": pull_request.head_sha,
            "pull_request_url": pull_request.html_url,
            "incident_id": None,
            "status": PrReviewStatus.ACKNOWLEDGED.value,
            "checks": [],
            "risk": None,
            "confidence": None,
            "summary": "",
            "findings": [],
            "merge": None,
            "decision_reason": "",
            "reviewed_at": None,
            "merged_at": None,
            "merge_commit_sha": "",
            "timeline": [],
            "attempts": [],
            "tool_budget": {},
        }

    def acknowledge_review(self, review_id: str, pull_request: PullRequest, incident_id: str | None = None) -> bool:
        event = Acknowledged(incident_id)
        outcome = self.apply_transition(review_id, event, pull_request)
        return isinstance(outcome, Accepted)

    def claim_review(self, review_id: str, request: PrReviewRequest, workflow_id: str) -> bool:
        pull_request = request.pull_request
        event = PrReviewClaimed(
            workflow_id, request.trigger, request.prompt, pull_request.base_sha, pull_request.head_sha
        )
        outcome = self.apply_transition(review_id, event, pull_request)
        return succeeded(outcome)

    def fail(self, record_id: str, workflow_id: str, failure: RunFailure) -> None:
        actions, budget = failure_trail(failure)
        event = PrReviewFailed(workflow_id, failure.error, actions, budget)
        self.apply_transition(record_id, event)

    def save_review(self, review_id: str, result: DecidedPrReview, workflow_id: str) -> bool:
        result_json = result.model_dump(mode="json")
        event = ResultSaved(workflow_id, result_json)
        outcome = self.apply_transition(review_id, event)
        require_existing(outcome, f"review not found: {review_id}")
        return isinstance(outcome, Accepted)

    def mark_merged(self, review_id: str, sha: str) -> None:
        event = Merged(sha)
        outcome = self.apply_transition(review_id, event)
        require_existing(outcome, f"review not found: {review_id}")

    def reject_replay(self, review_id: str, reason: str) -> None:
        event = ReplayRejected(reason)
        outcome = self.apply_transition(review_id, event)
        require_existing(outcome, f"review not found: {review_id}")

    def claim_fix(self, review_id: str, workflow_id: str, prompt: str) -> bool:
        event = FixClaimed(workflow_id, prompt)
        outcome = self.apply_transition(review_id, event)
        require_existing(outcome, f"review not found: {review_id}")
        return succeeded(outcome)

    def decline_fix(
        self, review_id: str, reason: str, workflow_id: str = "", proposal: ProposedPrFix | None = None
    ) -> None:
        proposal_json = None if proposal is None else proposal.model_dump(mode="json")
        event = FixDeclined(reason, workflow_id, proposal_json)
        outcome = self.apply_transition(review_id, event)
        require_existing(outcome, f"review not found: {review_id}")

    def save_fix(self, review_id: str, workflow_id: str, proposal: ProposedPrFix) -> bool:
        proposal_json = proposal.model_dump(mode="json")
        event = FixProposed(workflow_id, proposal_json)
        outcome = self.apply_transition(review_id, event)
        require_existing(outcome, f"review not found: {review_id}")
        return isinstance(outcome, Accepted)

    def mark_fix_pushed(self, review_id: str, workflow_id: str, sha: str) -> None:
        event = FixPushed(workflow_id, sha)
        outcome = self.apply_transition(review_id, event)
        require_existing(outcome, f"review not found: {review_id}")

    def delete(self, record_id: str) -> None:
        event = Deleted()
        outcome = self.apply_transition(record_id, event)
        require_allowed(outcome)

    def needs_review(self, pull_request: PullRequest) -> bool:
        review_id = self.id_for(pull_request)
        revision = (pull_request.base_sha, pull_request.head_sha)
        with self.database.sessions() as session:
            record = session.get(PrReviewRecord, review_id)
            if record is None:
                return rules.needs_review(None, revision, revision)
            reviewed = (record.base_sha, record.head_sha)
            return rules.needs_review(record.status, revision, reviewed)
