import logging
from typing import Protocol

from sentinel.core.contracts.reviews import PullRequest
from sentinel.workflow.sre.reviews.repository import PrReviewRepository

logger = logging.getLogger(__name__)

LINKED = "started"


class IncidentRecords(Protocol):
    def incident_for(self, pull_request_url: str) -> str | None: ...

    def record_fix_review(self, incident_id: str, review_id: str, status: str, reason: str = "") -> None: ...


class IncidentLink:
    """Attach a review to the incident whose fix pull request it reviews, and report the review back to it.

    A pull request is an incident's fix when the incident recorded its URL. The review keeps that incident; the
    incident records the review starting and every final review status with its reason. Reviews of any other pull
    request have no incident.
    """

    def __init__(self, reviews: PrReviewRepository, incidents: IncidentRecords):
        self.reviews = reviews
        self.incidents = incidents

    def acknowledge(self, review_id: str, pull_request: PullRequest) -> None:
        incident_id = self.incidents.incident_for(pull_request.html_url) if pull_request.html_url else None
        linked = self.reviews.acknowledge_review(review_id, pull_request, incident_id)
        if linked and incident_id is not None:
            self.incidents.record_fix_review(incident_id, review_id, LINKED)

    def report(self, review_id: str) -> None:
        try:
            review = self.reviews.get(review_id)
            incident_id = review["incident_id"] if review else None
            if incident_id is not None:
                self.incidents.record_fix_review(incident_id, review_id, review["status"], review["decision_reason"])
        except Exception:
            logger.exception("Could not report review %s to its incident", review_id)
