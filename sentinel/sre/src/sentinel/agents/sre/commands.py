import json
import subprocess
from pathlib import Path

from langchain_core.tools import ToolException
from sentinel.agents.sre.settings import Settings
from sentinel.core.commands.shell import execute_pipeline, validate_command
from sentinel.core.secrets import redact


class CommandRunner:
    def __init__(self, settings: Settings):
        self.settings = settings

    def run(self, command: str, timeout_seconds: int, working_directory: Path) -> str:
        try:
            segments = validate_command(command, self.settings.shell.allowed_binaries)
            max_bytes = self.settings.limits.max_tool_output_bytes
            output = execute_pipeline(segments, timeout_seconds, working_directory, max_bytes)
        except subprocess.TimeoutExpired as exc:
            raise ToolException("command timed out") from exc
        except (OSError, ValueError) as exc:
            raise ToolException(f"{exc}") from exc
        result = {"command": command, **output}
        redacted = self._redact(result)
        return json.dumps(redacted)

    def _redact(self, result: dict) -> dict:
        secrets = self.settings.known_secrets()
        redacted = dict(result)
        for field in ("command", "stdout", "stderr"):
            redacted[field] = redact(result[field], secrets)
        return redacted
