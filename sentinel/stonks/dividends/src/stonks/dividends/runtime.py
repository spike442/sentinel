from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass

from sentinel.agents.dividends.agent import DividendAgent
from sentinel.agents.dividends.tools import ResearchSources
from sentinel.agents.framework.prompts import PromptStore
from sentinel.agents.framework.runner import AgentRunner
from stonks.core.http import HttpSource, http_client
from stonks.core.objects import ObjectStore, s3_client
from stonks.dividends.config.settings import Settings
from stonks.dividends.sources.pages import PageReader
from stonks.dividends.sources.searxng import SearxngSearch
from stonks.dividends.storage.store import DividendStore

PROMPT_SCOPE = "stonks"


@dataclass(frozen=True)
class DividendRuntime:
    settings: Settings
    store: DividendStore
    reader: PageReader
    agent: DividendAgent


@contextmanager
def dividend_runtime(settings: Settings) -> Iterator[DividendRuntime]:
    with ExitStack() as resources:
        s3 = s3_client(settings)
        resources.callback(s3.close)
        client = http_client(settings.http)
        resources.callback(client.close)
        http = HttpSource(client, settings.http)
        search = SearxngSearch(http, settings.search)
        reader = PageReader(http, settings.pages)
        prompts = PromptStore(s3, settings.s3.bucket)
        sources = ResearchSources(search=search, reader=reader)
        runner = AgentRunner(settings.agent, settings.llm_api_key, prompts)
        resources.callback(runner.close)
        agent = DividendAgent(runner, sources, settings.pages, PROMPT_SCOPE)
        objects = ObjectStore(s3, settings.s3)
        store = DividendStore(objects, settings.storage)
        yield DividendRuntime(settings=settings, store=store, reader=reader, agent=agent)
