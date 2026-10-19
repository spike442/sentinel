from datetime import datetime

from sentinel.agents.pr_review.runtime import load_review
from sentinel.agents.pr_review.settings import Settings
from sentinel.core.contracts.reviews import PreparedPrReview
from sentinel.core.kafka.agent_worker import run_agent
from sentinel.core.kafka.consumer import exit_on_signals
from sentinel.core.kafka.contracts import KafkaTopic, RequestKind
from sentinel.core.observability.logging import configure_logging


def main() -> None:
    exit_on_signals()
    settings = Settings()
    configure_logging(settings.logging.level)
    with load_review(settings) as review_run:

        def process_message(payload: dict, deadline: datetime):
            request = PreparedPrReview.model_validate(payload)
            result = review_run.run(request, deadline)
            return result

        run_agent(
            settings,
            KafkaTopic.PR_REVIEW_COMMANDS,
            KafkaTopic.PR_REVIEW_RETURNS,
            RequestKind.PR_REVIEW,
            process_message,
            run_timeout_seconds=settings.review.run_timeout_seconds,
        )


if __name__ == "__main__":
    main()
