from datetime import datetime
from pathlib import Path
from typing import Any

from sentinel.agents.framework.knowledge import reference_material
from sentinel.agents.framework.runner import AgentRun, AgentRunner, AgentTask
from sentinel.agents.sre.review.tools import FIX_TOOLS, REVIEW_TOOLS, ToolContext
from sentinel.core.contracts.history import PriorAttempt
from sentinel.core.contracts.reviews import CheckResult, PreparedPrReview, PrFix, PrReviewResult, PullRequest
from sentinel.core.domain import AgentDomain, ReviewTrigger
from sentinel.core.knowledge import KnowledgeClient
from sentinel.core.observability.audit import AuditLog

REVIEW = AgentTask(
    agent=AgentDomain.PULL_REQUEST_REVIEW.value,
    action="review",
    tools=REVIEW_TOOLS,
    context_schema=ToolContext,
    answer=PrReviewResult,
)
FIX = AgentTask(
    agent=AgentDomain.PULL_REQUEST_REVIEW.value,
    action="fix",
    tools=FIX_TOOLS,
    context_schema=ToolContext,
    answer=PrFix,
)


class ReviewAgent:
    def __init__(self, runner: AgentRunner, knowledge: KnowledgeClient, max_file_bytes: int):
        self.runner = runner
        self.knowledge = knowledge
        self.max_file_bytes = max_file_bytes

    def generate_review(
        self, request: PreparedPrReview, diff: str, audit: AuditLog, deadline: datetime
    ) -> PrReviewResult:
        message = self.review_prompt(request, diff)
        run = self._run(REVIEW, request, message, audit=audit, deadline=deadline, checkout=None)
        review = self.runner.run(REVIEW, run)
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
        message = self.fix_prompt(request, diff, checks)
        run = self._run(FIX, request, message, audit=audit, deadline=deadline, checkout=checkout)
        fix = self.runner.run(FIX, run)
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
        template = self.runner.load_prompt(REVIEW, request.repository.name, "actions/replay.md")
        rendered = template.replace("{{operator_prompt}}", request.prompt)
        return f"\n\n{rendered}"

    def _run(
        self,
        task: AgentTask,
        request: PreparedPrReview,
        message: str,
        *,
        audit: AuditLog,
        deadline: datetime,
        checkout: Path | None,
    ) -> AgentRun:
        pull_request = request.pull_request
        context = ToolContext(
            audit=audit,
            deadline=deadline,
            knowledge=self.knowledge,
            repository=pull_request.repository,
            checkout=checkout,
            max_file_bytes=self.max_file_bytes,
        )
        return AgentRun(
            scope=request.repository.name,
            message=message,
            context=context,
            name=f"pr-{task.action}-{pull_request.repository}-{pull_request.number}",
            tags=[f"pr-{task.action}", pull_request.repository],
            metadata={
                "repository": pull_request.repository,
                "pull_request": pull_request.number,
                "head_sha": pull_request.head_sha,
                "trigger": request.trigger.value,
            },
        )


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
