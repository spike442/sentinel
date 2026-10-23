import logging
import threading
from collections.abc import Callable
from contextlib import ExitStack

from sentinel.core.config.workflow import IncidentSettings, PrReviewSettings, WorkflowAgents
from sentinel.core.domain import AgentDomain
from sentinel.core.github import READ_ONLY, GitHubAppAuth, GitHubReader
from sentinel.core.kafka.consumer import exit_on_signals
from sentinel.core.kafka.contracts import KafkaTopic
from sentinel.core.knowledge import KnowledgeClient
from sentinel.core.observability.logging import configure_logging
from sentinel.core.persistence.postgres import PostgresDatabase
from sentinel.workflow.discord import DiscordWebhook
from sentinel.workflow.routing import SHARED_TOPICS, DomainRouter, DomainWorkflow, Handler
from sentinel.workflow.runner import Route, run
from sentinel.workflow.sre.incidents.alertmanager import AlertmanagerClient
from sentinel.workflow.sre.incidents.repository import IncidentRepository
from sentinel.workflow.sre.incidents.workflow import IncidentWorkflow
from sentinel.workflow.sre.reviews.repository import PrReviewRepository
from sentinel.workflow.sre.reviews.workflow import PrReviewWorkflow

logger = logging.getLogger(__name__)

Job = Callable[[threading.Event], None]


def every(seconds: int, action: Callable[[], None], failure: str) -> Job:
    def job(stopped: threading.Event) -> None:
        while not stopped.is_set():
            try:
                action()
            except Exception:
                logger.exception(failure)
            stopped.wait(seconds)

    return job


def topic_routes(workflows: list[DomainWorkflow]) -> list[Route]:
    routes: list[Route] = []
    shared: dict[KafkaTopic, dict[AgentDomain, Handler]] = {topic: {} for topic in SHARED_TOPICS}
    for workflow in workflows:
        for topic in workflow.topics:
            if topic in shared:
                shared[topic][workflow.domain] = workflow.route_message
            else:
                routes.append((topic, workflow.route_message))
    for topic, handlers in shared.items():
        router = DomainRouter(handlers)
        routes.append((topic, router.route_message))
    return routes


def main() -> None:
    exit_on_signals()
    selection = WorkflowAgents()
    enabled = selection.agents
    configure_logging(selection.logging.level)
    if not enabled:
        raise RuntimeError("the workflow needs at least one enabled agent")
    incident_settings = IncidentSettings() if AgentDomain.SRE in enabled else None
    review_settings = PrReviewSettings() if AgentDomain.PULL_REQUEST_REVIEW in enabled else None
    settings = incident_settings or review_settings
    workflows: list[DomainWorkflow] = []
    jobs: list[Job] = []
    with ExitStack() as resources:
        database = PostgresDatabase(settings.database_dsn)
        resources.callback(database.close)
        knowledge = KnowledgeClient(settings.knowledge.endpoint)
        resources.callback(knowledge.close)
        discord = DiscordWebhook(settings.discord_webhook_url)
        resources.callback(discord.close)
        incidents = IncidentRepository(database)
        if incident_settings is not None:
            alertmanager = AlertmanagerClient(incident_settings.alertmanager.url)
            resources.callback(alertmanager.close)
            incident_workflow = IncidentWorkflow(incident_settings, incidents, knowledge, alertmanager, discord)
            workflows.append(incident_workflow)
            jobs.append(every(60, incident_workflow.expire_workflows, "Could not expire stalled incident workflows"))
        if review_settings is not None:
            reviews = PrReviewRepository(database)
            private_key = review_settings.github_private_key.get_secret_value()
            github_auth = GitHubAppAuth(
                review_settings.github_app_id, review_settings.github_installation_id, private_key, READ_ONLY
            )
            github = GitHubReader(github_auth)
            resources.callback(github.close)
            review_workflow = PrReviewWorkflow(
                review_settings, reviews, knowledge, github, discord, incidents=incidents
            )
            workflows.append(review_workflow)
            poll = every(
                review_settings.review_poll_seconds,
                review_workflow.schedule_discovery,
                "Could not schedule PR discovery",
            )
            expire = every(60, review_workflow.expire_workflows, "Could not expire stalled review workflows")
            jobs.extend([poll, expire])
        routes = topic_routes(workflows)
        run(settings, routes, jobs)


if __name__ == "__main__":
    main()
