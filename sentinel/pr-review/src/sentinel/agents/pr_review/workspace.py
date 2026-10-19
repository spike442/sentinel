import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sentinel.core.contracts.changes import ProposedChange
from sentinel.core.contracts.reviews import CheckResult, PullRequest, RepositoryConfig
from sentinel.core.deadline import RunTimedOut, remaining_seconds
from sentinel.core.observability.audit import AuditLog
from sentinel.core.secrets import contains_secret

WORKSPACE_ROOT = Path("/tmp/pr-review")


def checkout_path(checkout: Path, file_path: str) -> Path | None:
    root = checkout.resolve()
    target = (root / file_path).resolve()
    if root not in target.parents:
        return None
    relative = target.relative_to(root)
    if relative.parts[0] == ".git":
        return None
    return target


def read_checkout_file(checkout: Path | None, file_path: str, max_bytes: int) -> str:
    target = None if checkout is None else checkout_path(checkout, file_path)
    if target is None:
        return f"Refused: {file_path} is not a file of this repository."
    if not target.is_file():
        return f"No file at {file_path}."
    content = target.read_bytes()
    if len(content) > max_bytes:
        return f"Refused: {file_path} is larger than {max_bytes} bytes; propose no change to it."
    text = content.decode(errors="replace")
    if contains_secret(text):
        return f"Refused: {file_path} contains credential material; propose no change to it."
    return text


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
