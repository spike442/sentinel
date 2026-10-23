from datetime import datetime

from sentinel.core.contracts.incidents import IncidentResult, PreparedIncident
from sentinel.core.contracts.reviews import DecidedPrReview, PreparedPrReview, ProposedPrFix
from sentinel.core.kafka.agent_worker import Agent, run_agents
from sentinel.core.kafka.consumer import exit_on_signals
from sentinel.core.kafka.contracts import KafkaTopic, RequestKind, RunFailure
from sentinel.core.observability.logging import configure_logging
from sentinel.sre.incidents.runtime import load_investigation
from sentinel.sre.incidents.settings import Settings as IncidentSettings
from sentinel.sre.reviews.runtime import load_review
from sentinel.sre.reviews.settings import Settings as ReviewSettings


def main() -> None:
    exit_on_signals()
    incident_settings = IncidentSettings()
    review_settings = ReviewSettings()
    configure_logging(incident_settings.logging.level)
    with load_investigation(incident_settings) as investigation, load_review(review_settings) as review_run:

        def investigate(payload: dict, deadline: datetime) -> IncidentResult | RunFailure:
            request = PreparedIncident.model_validate(payload)
            return investigation.investigate(request, deadline)

        def review(payload: dict, deadline: datetime) -> DecidedPrReview | ProposedPrFix | RunFailure:
            request = PreparedPrReview.model_validate(payload)
            return review_run.run(request, deadline)

        incidents = Agent(
            settings=incident_settings,
            topic=KafkaTopic.SRE_COMMANDS,
            return_topic=KafkaTopic.SRE_RETURNS,
            kind=RequestKind.INCIDENT,
            execute=investigate,
            run_timeout_seconds=incident_settings.limits.run_timeout_seconds,
        )
        reviews = Agent(
            settings=review_settings,
            topic=KafkaTopic.PR_REVIEW_COMMANDS,
            return_topic=KafkaTopic.PR_REVIEW_RETURNS,
            kind=RequestKind.PR_REVIEW,
            execute=review,
            run_timeout_seconds=review_settings.review.run_timeout_seconds,
        )
        run_agents([incidents, reviews])


if __name__ == "__main__":
    main()
