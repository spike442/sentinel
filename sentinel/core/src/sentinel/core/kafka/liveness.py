import logging

from confluent_kafka.admin import AdminClient
from sentinel.core.config.settings import KafkaClientSettings
from sentinel.core.domain import AgentDomain
from sentinel.core.kafka.config import client_config
from sentinel.core.kafka.contracts import RequestKind

logger = logging.getLogger(__name__)

AGENT_REQUEST_KINDS = {AgentDomain.SRE: RequestKind.INCIDENT, AgentDomain.PULL_REQUEST_REVIEW: RequestKind.PR_REVIEW}
DESCRIBE_TIMEOUT_SECONDS = 5


class AgentLiveness:
    def __init__(self, settings: KafkaClientSettings):
        self._consumer_group = settings.kafka.consumer_group
        config = client_config(settings)
        self._admin = AdminClient(config)

    def consuming(self, domains: list[AgentDomain]) -> set[AgentDomain]:
        groups = {f"{self._consumer_group}-{AGENT_REQUEST_KINDS[domain].value}": domain for domain in domains}
        if not groups:
            return set()
        futures = self._admin.describe_consumer_groups(list(groups), request_timeout=DESCRIBE_TIMEOUT_SECONDS)
        running: set[AgentDomain] = set()
        for group, future in futures.items():
            try:
                description = future.result()
            except Exception as exc:
                logger.warning("Consumer group unavailable group=%s error=%s", group, exc)
                continue
            if description.members:
                running.add(groups[group])
        return running
