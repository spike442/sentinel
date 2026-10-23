import json
import subprocess
from pathlib import Path

from langchain_core.tools import ToolException
from sentinel.agents.sre.incident.settings import ShellConfig
from sentinel.core.commands.shell import execute_pipeline, validate_command
from sentinel.core.secrets import redact


class CommandRunner:
    def __init__(self, shell: ShellConfig, max_output_bytes: int, known_secrets: tuple[str, ...]):
        self.shell = shell
        self.max_output_bytes = max_output_bytes
        self.known_secrets = known_secrets

    def run(self, command: str, timeout_seconds: int, working_directory: Path) -> str:
        try:
            segments = validate_command(command, self.shell.allowed_binaries)
            output = execute_pipeline(segments, timeout_seconds, working_directory, self.max_output_bytes)
        except subprocess.TimeoutExpired as exc:
            raise ToolException("command timed out") from exc
        except (OSError, ValueError) as exc:
            raise ToolException(f"{exc}") from exc
        result = {"command": command, **output}
        redacted = self._redact(result)
        return json.dumps(redacted)

    def _redact(self, result: dict) -> dict:
        redacted = dict(result)
        for field in ("command", "stdout", "stderr"):
            redacted[field] = redact(result[field], self.known_secrets)
        return redacted
