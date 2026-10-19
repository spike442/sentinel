from datetime import datetime

from sentinel.agents.sre.runtime import load_investigation
from sentinel.agents.sre.settings import Settings
from sentinel.core.contracts.incidents import PreparedIncident
from sentinel.core.kafka.agent_worker import run_agent
from sentinel.core.kafka.consumer import exit_on_signals
from sentinel.core.kafka.contracts import KafkaTopic, RequestKind
from sentinel.core.observability.logging import configure_logging


def main() -> None:
    exit_on_signals()
    settings = Settings()
    configure_logging(settings.logging.level)
    with load_investigation(settings) as investigation:

        def process_message(payload: dict, deadline: datetime):
            request = PreparedIncident.model_validate(payload)
            result = investigation.investigate(request, deadline)
            return result

        run_agent(
            settings,
            KafkaTopic.SRE_COMMANDS,
            KafkaTopic.SRE_RETURNS,
            RequestKind.INCIDENT,
            process_message,
            run_timeout_seconds=settings.limits.run_timeout_seconds,
        )


if __name__ == "__main__":
    main()
