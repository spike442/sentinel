from collections.abc import Iterator
from contextlib import ExitStack, contextmanager

from sentinel.agents.sre.agent import DiagnosisAgent
from sentinel.agents.sre.commands import CommandRunner
from sentinel.agents.sre.run import IncidentInvestigation
from sentinel.agents.sre.settings import Settings
from sentinel.core.agents.prompts import PromptStore
from sentinel.core.knowledge import KnowledgeClient


@contextmanager
def load_investigation(settings: Settings) -> Iterator[IncidentInvestigation]:
    with ExitStack() as resources:
        secret_access_key = settings.s3_secret_access_key.get_secret_value()
        prompts = PromptStore(settings.s3, settings.s3_access_key_id, secret_access_key)
        resources.callback(prompts.close)
        knowledge = KnowledgeClient(settings.knowledge.endpoint)
        resources.callback(knowledge.close)
        commands = CommandRunner(settings)
        agent = DiagnosisAgent(settings, prompts, commands, knowledge)
        resources.callback(agent.close)
        yield IncidentInvestigation(agent)
