from collections.abc import Iterator
from contextlib import ExitStack, contextmanager

from sentinel.agents.framework.prompts import PromptStore
from sentinel.agents.framework.runner import AgentRunner
from sentinel.agents.sre.review.agent import ReviewAgent
from sentinel.core.knowledge import KnowledgeClient
from sentinel.core.s3 import s3_client
from sentinel.sre.reviews.run import ReviewRun
from sentinel.sre.reviews.settings import Settings
from sentinel.sre.reviews.workspace import WorkspaceManager


@contextmanager
def load_review(settings: Settings) -> Iterator[ReviewRun]:
    with ExitStack() as resources:
        secret_access_key = settings.s3_secret_access_key.get_secret_value()
        s3 = s3_client(settings.s3, settings.s3_access_key_id, secret_access_key)
        resources.callback(s3.close)
        prompts = PromptStore(s3, settings.s3.bucket)
        knowledge = KnowledgeClient(settings.knowledge.endpoint)
        resources.callback(knowledge.close)
        runner = AgentRunner(settings.agent, settings.openai_api_key, prompts)
        resources.callback(runner.close)
        review = settings.review
        agent = ReviewAgent(runner, knowledge, review.max_file_bytes)
        workspace = WorkspaceManager(review.max_command_output_bytes)
        yield ReviewRun(settings, workspace, agent)
