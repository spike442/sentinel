from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel
from sentinel.agents.pr_review.settings import Settings
from sentinel.agents.pr_review.tools import FIX_TOOLS, REVIEW_TOOLS, ToolContext
from sentinel.core.agents.langchain import chat_model, reference_material, structured_agent, tool_budget
from sentinel.core.agents.prompts import PromptStore
from sentinel.core.contracts.history import PriorAttempt
from sentinel.core.contracts.reviews import CheckResult, PreparedPrReview, PrFix, PrReviewResult, PullRequest
from sentinel.core.deadline import remaining_seconds
from sentinel.core.digest import text_digest
from sentinel.core.domain import ReviewTrigger
from sentinel.core.knowledge import KnowledgeClient
from sentinel.core.observability.audit import AuditLog

TASKS: dict[ReviewTrigger, tuple[str, dict[str, BaseTool], type[BaseModel]]] = {
    ReviewTrigger.REVIEW: ("review", REVIEW_TOOLS, PrReviewResult),
    ReviewTrigger.REPLAY: ("review", REVIEW_TOOLS, PrReviewResult),
    ReviewTrigger.FIX: ("fix", FIX_TOOLS, PrFix),
}


class ReviewAgent:
    def __init__(self, settings: Settings, knowledge: KnowledgeClient, prompts: PromptStore):
        self.model = chat_model(settings.llm, settings.openai_api_key)
        self.max_tool_calls = settings.review.max_tool_calls
        self.max_file_bytes = settings.review.max_file_bytes
        self.knowledge = knowledge
        self.prompts = prompts
        self._agents: dict[tuple[str, str], Any] = {}

    def generate_review(
        self, request: PreparedPrReview, diff: str, audit: AuditLog, deadline: datetime
    ) -> PrReviewResult:
        prompt = self.review_prompt(request, diff)
        review = self._invoke(request, prompt, audit, deadline, None)
        submitted = review.model_dump(mode="json")
        audit.record("review_submitted", submitted)
        return review

    def generate_fix(
        self,
        request: PreparedPrReview,
        diff: str,
        checks: list[CheckResult],
        *,
        checkout: Path,
        audit: AuditLog,
        deadline: datetime,
    ) -> PrFix:
        prompt = self.fix_prompt(request, diff, checks)
        fix = self._invoke(request, prompt, audit, deadline, checkout)
        changed = [change.file_path for change in fix.changes]
        audit.record("fix_proposed", {"summary": fix.summary, "commit_message": fix.commit_message, "files": changed})
        return fix

    def review_prompt(self, request: PreparedPrReview, diff: str) -> str:
        pull_request = request.pull_request
        references = reference_material(request.rag_context)
        facts = pull_request_facts(pull_request)
        earlier = attempt_history(request.history)
        operator = self._replay_instruction(request)
        return (
            f"Review pull request #{pull_request.number} in "
            f"{pull_request.owner}/{pull_request.repository}.\n\n"
            f"{facts}{earlier}{operator}\n\n"
            f"Diff:\n{diff}{references}"
        )

    def fix_prompt(self, request: PreparedPrReview, diff: str, checks: list[CheckResult]) -> str:
        pull_request = request.pull_request
        references = reference_material(request.rag_context)
        facts = pull_request_facts(pull_request)
        earlier = attempt_history(request.history)
        instruction = f"\n\nOperator instruction:\n{request.prompt}" if request.prompt else ""
        check_lines = [check_summary(check) for check in checks]
        check_text = "\n".join(check_lines)
        return (
            f"Fix the blocked pull request #{pull_request.number} in "
            f"{pull_request.owner}/{pull_request.repository}.\n\n"
            f"{facts}{earlier}{instruction}\n\n"
            f"Checks of the head revision:\n{check_text}\n\n"
            f"Diff:\n{diff}{references}"
        )

    def _replay_instruction(self, request: PreparedPrReview) -> str:
        if request.trigger is not ReviewTrigger.REPLAY or not request.prompt:
            return ""
        template = self.prompts.load_text(request.repository.name, "pr-review", "actions/replay.md")
        rendered = template.replace("{{operator_prompt}}", request.prompt)
        return f"\n\n{rendered}"

    def _invoke(
        self, request: PreparedPrReview, prompt: str, audit: AuditLog, deadline: datetime, checkout: Path | None
    ) -> Any:
        pull_request = request.pull_request
        action, tools, response_format = TASKS[request.trigger]
        agent = self._agent_for(request.repository.name, action, tools, response_format)
        context = ToolContext(
            audit=audit,
            knowledge=self.knowledge,
            repository=pull_request.repository,
            deadline=deadline,
            checkout=checkout,
            max_file_bytes=self.max_file_bytes,
        )
        result = agent.invoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config={
                "run_name": f"pr-{action}-{pull_request.repository}-{pull_request.number}",
                "tags": [f"pr-{action}", pull_request.repository],
                "metadata": {
                    "repository": pull_request.repository,
                    "pull_request": pull_request.number,
                    "head_sha": pull_request.head_sha,
                    "trigger": request.trigger.value,
                },
            },
            context=context,
        )
        remaining_seconds(deadline)
        tool_names = list(tools)
        budget = tool_budget(result["messages"], tool_names, self.max_tool_calls)
        audit.record_tool_budget(budget)
        answer = result.get("structured_response")
        if not isinstance(answer, response_format):
            raise ValueError(f"LangChain did not return a structured {action}")
        return answer

    def _agent_for(
        self, repository: str, action: str, tools: dict[str, BaseTool], response_format: type[BaseModel]
    ) -> Any:
        agent = self._agents.get((repository, action))
        if agent is None:
            system_prompt = self.prompts.load_text(repository, "pr-review", "system.md")
            action_prompt = self.prompts.load_text(repository, "pr-review", f"actions/{action}.md")
            instructions = f"{action_prompt}\n\nReviewer instructions:\n{system_prompt}"
            prompt_version = text_digest(instructions)[:16]
            agent = structured_agent(
                self.model,
                cache_key=f"pr-{action}:{repository}:{prompt_version}",
                tools=tools.values(),
                context_schema=ToolContext,
                system_prompt=instructions,
                response_format=response_format,
                max_tool_calls=self.max_tool_calls,
            )
            self._agents[(repository, action)] = agent
        return agent

    def close(self) -> None:
        self.model.root_client.close()


def pull_request_facts(pull_request: PullRequest) -> str:
    labels = ", ".join(pull_request.labels)
    return (
        f"Title: {pull_request.title}\n"
        f"Author: {pull_request.author}\n"
        f"Head branch: {pull_request.head_ref}\n"
        f"Labels: {labels}\n"
        f"Head SHA: {pull_request.head_sha}"
    )


def check_summary(check: CheckResult) -> str:
    outcome = "passed" if check.passed else "failed"
    output = f"\n{check.output}" if check.output else ""
    return f"- {check.name}: {outcome}{output}"


def attempt_history(history: list[PriorAttempt]) -> str:
    if not history:
        return ""
    lines = ["\n\nEarlier attempts on this pull request:"]
    for attempt in history:
        head = attempt.head_sha[:12]
        heading = f"- Attempt {attempt.number} ({attempt.trigger}) of head {head} at {attempt.started_at}"
        lines.append(f"{heading}: {attempt.status}")
        if attempt.prompt:
            lines.append(f"  operator instruction: {attempt.prompt}")
        lines.extend(attempt_result(attempt.result))
    return "\n".join(lines)


def attempt_result(result: dict[str, Any]) -> list[str]:
    lines = []
    if result.get("decision_reason"):
        lines.append(f"  decision: {result['decision_reason']}")
    if result.get("summary"):
        lines.append(f"  summary: {result['summary']}")
    lines.extend(f"  finding: {finding}" for finding in result.get("findings", []))
    for check in result.get("checks", []):
        if not check["passed"]:
            lines.append(f"  failed check {check['name']}: {check.get('output', '')}")
    changed = [change["file_path"] for change in result.get("changes", [])]
    if changed:
        files = ", ".join(changed)
        lines.append(f"  fix changed: {files}")
    if result.get("commit_sha"):
        lines.append(f"  fix pushed as {result['commit_sha']}")
    if result.get("reason"):
        lines.append(f"  fix declined: {result['reason']}")
    if result.get("error"):
        lines.append(f"  error: {result['error']}")
    return lines
