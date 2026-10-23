import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sentinel.agents.sre.review.checkout import checkout_path
from sentinel.core.contracts.changes import ProposedChange
from sentinel.core.contracts.reviews import CheckResult, PullRequest, RepositoryConfig
from sentinel.core.deadline import RunTimedOut, remaining_seconds
from sentinel.core.observability.audit import AuditLog

WORKSPACE_ROOT = Path("/tmp/pr-review")


class WorkspaceManager:
    def __init__(self, max_output_bytes: int):
        self.root = WORKSPACE_ROOT
        self.max_output_bytes = max_output_bytes

    @contextmanager
    def checkout_repository(
        self, pull_request: PullRequest, repository: RepositoryConfig, audit: AuditLog, deadline: datetime
    ):
        self.root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f"pr-{pull_request.number}-", dir=self.root) as temporary_directory:
            workspace = Path(temporary_directory)
            self._run_command(
                [
                    "git",
                    "clone",
                    "--depth",
                    str(repository.clone_depth),
                    "--no-checkout",
                    repository.clone_url,
                    str(workspace),
                ],
                self.root,
                audit,
                deadline,
            )
            self._run_command(
                ["git", "fetch", "origin", f"pull/{pull_request.number}/head"], workspace, audit, deadline
            )
            self._run_command(["git", "fetch", "origin", pull_request.base_sha], workspace, audit, deadline)
            self._run_command(["git", "checkout", "--detach", pull_request.head_sha], workspace, audit, deadline)
            yield workspace

    def run_checks(
        self, checkout: Path, pull_request: PullRequest, audit: AuditLog, deadline: datetime
    ) -> list[CheckResult]:
        command = ["git", "diff", "--check", pull_request.base_sha, pull_request.head_sha]
        result = self._run_command(command, checkout, audit, deadline, check=False)
        return [CheckResult(name="git diff --check", passed=result.returncode == 0, output=result.stdout)]

    def check_fix(
        self,
        checkout: Path,
        pull_request: PullRequest,
        changes: list[ProposedChange],
        audit: AuditLog,
        deadline: datetime,
    ) -> list[CheckResult]:
        for change in changes:
            target = checkout_path(checkout, change.file_path)
            if target is None:
                output = f"{change.file_path} is not a file of this repository."
                return [CheckResult(name="change paths", passed=False, output=output)]
            if change.delete:
                if not target.is_file():
                    output = f"{change.file_path} deletes a file that does not exist."
                    return [CheckResult(name="change paths", passed=False, output=output)]
                target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(change.content, encoding="utf-8")
        paths = [change.file_path for change in changes]
        self._run_command(["git", "add", "--", *paths], checkout, audit, deadline)
        command = ["git", "diff", "--cached", "--check", pull_request.base_sha]
        result = self._run_command(command, checkout, audit, deadline, check=False)
        return [CheckResult(name="git diff --check", passed=result.returncode == 0, output=result.stdout)]

    def read_diff(
        self, checkout: Path, pull_request: PullRequest, audit: AuditLog, deadline: datetime, max_bytes: int
    ) -> str:
        result = self._run_command(
            ["git", "diff", "--no-ext-diff", "--unified=80", pull_request.base_sha, pull_request.head_sha],
            checkout,
            audit,
            deadline,
            output_limit=max_bytes,
        )
        return result.stdout

    def _run_command(
        self,
        command: list[str],
        cwd: Path,
        audit: AuditLog,
        deadline: datetime,
        *,
        check: bool = True,
        output_limit: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        limit = output_limit or self.max_output_bytes
        timeout = remaining_seconds(deadline)
        details: dict = {"command": command, "exit_code": None, "output": "", "output_truncated": False}
        try:
            with tempfile.TemporaryFile() as output:
                completed = subprocess.run(
                    command, cwd=cwd, check=False, stdout=output, stderr=subprocess.STDOUT, timeout=timeout
                )
                output.seek(0)
                captured = output.read(limit + 1)
        except (OSError, subprocess.TimeoutExpired) as exc:
            details["output"] = type(exc).__name__
            audit.record("workspace_command", details)
            if isinstance(exc, subprocess.TimeoutExpired):
                raise RunTimedOut("the workspace command did not finish before the run's deadline") from exc
            raise
        stdout = captured[:limit].decode(errors="replace")
        encoded = stdout.encode()
        recorded = encoded[-self.max_output_bytes :].decode(errors="replace")
        details.update(exit_code=completed.returncode, output=recorded, output_truncated=len(captured) > limit)
        audit.record("workspace_command", details)
        if check and completed.returncode:
            raise subprocess.CalledProcessError(completed.returncode, command, output=stdout)
        return subprocess.CompletedProcess(command, completed.returncode, stdout)
