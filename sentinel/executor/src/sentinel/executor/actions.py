import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel
from sentinel.core.contracts.executor import (
    CreatePullRequest,
    FixPushed,
    MergeOutcome,
    MergePullRequest,
    MergeStatus,
    PullRequestCreated,
    PushFix,
    RunCommand,
)
from sentinel.core.contracts.incidents import ActionOutput
from sentinel.core.deadline import deadline_after
from sentinel.core.github import clean_and_mergeable, merged_commit, rejected
from sentinel.core.kafka.contracts import ExecutorAction, ExecutorCommand
from sentinel.executor import commands
from sentinel.executor.git_workspace import GitWorkspace
from sentinel.executor.github import GitHubGateway
from sentinel.executor.settings import ExecutorConfig

logger = logging.getLogger(__name__)

WORKSPACE = Path("/tmp/sentinel-executor")


class Executor:
    def __init__(self, config: ExecutorConfig, github: GitHubGateway, git: GitWorkspace):
        self.config = config
        self.github = github
        self.git = git

    def execute_command(self, command: ExecutorCommand) -> BaseModel:
        model, handler = HANDLERS[command.action]
        request = model.model_validate(command.payload)
        return handler(self, request)

    def create_pull_request(self, request: CreatePullRequest) -> PullRequestCreated:
        repository = request.repository
        existing = self.github.find_pull_request(repository, request.base_branch, request.branch)
        if existing and rejected(existing):
            return PullRequestCreated(url=existing["html_url"], rejected=True)
        if existing:
            self.github.add_labels(repository, existing["number"], request.labels)
            return PullRequestCreated(url=existing["html_url"])
        started_at = datetime.now(UTC)
        deadline = deadline_after(started_at, self.config.action_timeout_seconds)
        self.git.push_changes(
            repository, request.base_branch, request.changes, request.branch, title=request.title, deadline=deadline
        )
        url = self.github.create_pull_request(
            repository,
            base_branch=request.base_branch,
            head_branch=request.branch,
            title=request.title,
            body=request.body,
            labels=request.labels,
        )
        return PullRequestCreated(url=url)

    def merge_pull_request(self, request: MergePullRequest) -> MergeOutcome:
        pull_request = request.pull_request
        current = self.github.current(pull_request.owner, pull_request.repository, pull_request.number)
        merged_sha = merged_commit(current, pull_request.head_sha)
        if merged_sha:
            return MergeOutcome(status=MergeStatus.MERGED, sha=merged_sha)
        if not clean_and_mergeable(current):
            return MergeOutcome(status=MergeStatus.NOT_MERGEABLE)
        sha = self.github.merge_pull_request(pull_request, request.merge_method)
        logger.info(
            "Pull request merged repository=%s number=%s sha=%s", pull_request.repository, pull_request.number, sha
        )
        return MergeOutcome(status=MergeStatus.MERGED, sha=sha)

    def push_fix(self, request: PushFix) -> FixPushed:
        started_at = datetime.now(UTC)
        deadline = deadline_after(started_at, self.config.action_timeout_seconds)
        sha = self.git.push_fix(
            request.repository, request.branch, request.head_sha, request.changes, request.message, deadline=deadline
        )
        logger.info("Fix pushed repository=%s branch=%s sha=%s", request.repository.name, request.branch, sha)
        return FixPushed(sha=sha)

    def run_command(self, request: RunCommand) -> ActionOutput:
        return commands.run_command(request, self.config.commands, WORKSPACE / "commands")


HANDLERS: dict[ExecutorAction, tuple[type[BaseModel], Callable[[Executor, BaseModel], BaseModel]]] = {
    ExecutorAction.CREATE_PULL_REQUEST: (CreatePullRequest, Executor.create_pull_request),
    ExecutorAction.MERGE_PULL_REQUEST: (MergePullRequest, Executor.merge_pull_request),
    ExecutorAction.PUSH_FIX: (PushFix, Executor.push_fix),
    ExecutorAction.RUN_COMMAND: (RunCommand, Executor.run_command),
}
