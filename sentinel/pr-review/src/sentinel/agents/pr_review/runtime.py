from collections.abc import Iterator
from contextlib import ExitStack, contextmanager

from sentinel.agents.pr_review.agent import ReviewAgent
from sentinel.agents.pr_review.run import ReviewRun
from sentinel.agents.pr_review.settings import Settings
from sentinel.agents.pr_review.workspace import WorkspaceManager
from sentinel.core.agents.prompts import PromptStore
from sentinel.core.knowledge import KnowledgeClient


@contextmanager
def load_review(settings: Settings) -> Iterator[ReviewRun]:
    with ExitStack() as resources:
        secret_access_key = settings.s3_secret_access_key.get_secret_value()
        prompts = PromptStore(settings.s3, settings.s3_access_key_id, secret_access_key)
        resources.callback(prompts.close)
        knowledge = KnowledgeClient(settings.knowledge.endpoint)
        resources.callback(knowledge.close)
        agent = ReviewAgent(settings, knowledge, prompts)
        resources.callback(agent.close)
        review = settings.review
        workspace = WorkspaceManager(review.max_command_output_bytes)
        yield ReviewRun(settings, workspace, agent)
