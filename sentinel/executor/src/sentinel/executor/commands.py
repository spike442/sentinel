import shlex
import subprocess
from pathlib import Path

from sentinel.core.commands.shell import MAX_COMMAND_LENGTH, execute_pipeline
from sentinel.core.contracts.executor import RunCommand
from sentinel.core.contracts.incidents import ActionOutput
from sentinel.core.domain import ActionStatus
from sentinel.core.secrets import redact
from sentinel.executor.settings import CommandLimits


def parse_command(command: str) -> list[str]:
    if not command or len(command) > MAX_COMMAND_LENGTH:
        raise ValueError(f"command must be between 1 and {MAX_COMMAND_LENGTH} characters")
    try:
        arguments = shlex.split(command)
    except ValueError as exc:
        raise ValueError("invalid command syntax") from exc
    if not arguments:
        raise ValueError("command is empty")
    return arguments


def run_command(request: RunCommand, limits: CommandLimits, cwd: Path) -> ActionOutput:
    try:
        arguments = parse_command(request.command)
    except ValueError as exc:
        reason = str(exc)
        return ActionOutput(status=ActionStatus.FAILED, error="CommandRejected", reason=reason)
    cwd.mkdir(parents=True, exist_ok=True)
    try:
        result = execute_pipeline(
            [arguments],
            request.timeout_seconds,
            cwd,
            limits.max_output_bytes,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        error_type = type(exc).__name__
        return ActionOutput(status=ActionStatus.FAILED, error=error_type)
    status = ActionStatus.SUCCEEDED if result["exit_code"] == 0 else ActionStatus.FAILED
    stdout = redact(result["stdout"])
    stderr = redact(result["stderr"])
    return ActionOutput(status=status, exit_code=result["exit_code"], stdout=stdout, stderr=stderr)
