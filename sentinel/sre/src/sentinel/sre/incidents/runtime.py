from collections.abc import Iterator
from contextlib import ExitStack, contextmanager

from sentinel.agents.framework.prompts import PromptStore
from sentinel.agents.framework.runner import AgentRunner
from sentinel.agents.sre.incident.agent import DiagnosisAgent
from sentinel.agents.sre.incident.commands import CommandRunner
from sentinel.agents.sre.incident.prometheus import Prometheus
from sentinel.core.knowledge import KnowledgeClient
from sentinel.core.s3 import s3_client
from sentinel.sre.incidents.run import IncidentInvestigation
from sentinel.sre.incidents.settings import Settings


@contextmanager
def load_investigation(settings: Settings) -> Iterator[IncidentInvestigation]:
    with ExitStack() as resources:
        secret_access_key = settings.s3_secret_access_key.get_secret_value()
        s3 = s3_client(settings.s3, settings.s3_access_key_id, secret_access_key)
        resources.callback(s3.close)
        prompts = PromptStore(s3, settings.s3.bucket)
        knowledge = KnowledgeClient(settings.knowledge.endpoint)
        resources.callback(knowledge.close)
        runner = AgentRunner(settings.agent, settings.openai_api_key, prompts)
        resources.callback(runner.close)
        secrets = settings.known_secrets()
        max_output_bytes = settings.limits.max_tool_output_bytes
        commands = CommandRunner(settings.shell, max_output_bytes, secrets)
        prometheus = Prometheus(settings.prometheus, max_output_bytes, secrets)
        agent = DiagnosisAgent(runner, commands, prometheus, knowledge)
        yield IncidentInvestigation(agent)
