import json
from datetime import date, datetime

from sentinel.agents.dividends.contracts import DividendAnswer, Security
from sentinel.agents.dividends.settings import ExcerptConfig
from sentinel.agents.dividends.tools import TOOLS, ResearchSources, ToolContext
from sentinel.agents.framework.runner import AgentRun, AgentRunner, AgentTask
from sentinel.core.observability.audit import AuditLog

RESEARCH = AgentTask(
    agent="dividends",
    action="research",
    tools=TOOLS,
    context_schema=ToolContext,
    answer=DividendAnswer,
)


class DividendAgent:
    def __init__(self, runner: AgentRunner, sources: ResearchSources, excerpt: ExcerptConfig, scope: str):
        self.runner = runner
        self.sources = sources
        self.excerpt = excerpt
        self.scope = scope

    def research(self, security: Security, as_of: date, audit: AuditLog, deadline: datetime) -> DividendAnswer:
        message = research_request(security, as_of)
        context = ToolContext(audit=audit, deadline=deadline, sources=self.sources, excerpt=self.excerpt)
        run = AgentRun(
            scope=self.scope,
            message=message,
            context=context,
            name=f"dividends-{security.isin}",
            tags=[RESEARCH.agent, security.country],
            metadata={"isin": security.isin, "symbol": security.listing_symbol, "as_of": as_of.isoformat()},
        )
        answer = self.runner.run(RESEARCH, run)
        completed = answer.model_dump(mode="json")
        audit.record("research_completed", completed)
        return answer


def research_request(security: Security, as_of: date) -> str:
    fields = security.model_dump(mode="json")
    security_json = json.dumps(fields, indent=2)
    return (
        f"Find the next upcoming dividend of this security, as of {as_of.isoformat()}, "
        f"and follow the research instructions.\n\nSecurity:\n{security_json}"
    )
