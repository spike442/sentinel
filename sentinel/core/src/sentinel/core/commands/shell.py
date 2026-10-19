import os
import re
import shlex
import subprocess
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

MAX_COMMAND_LENGTH = 2000

KUBECTL_READ_ONLY_COMMANDS = frozenset(
    {"get", "describe", "logs", "top", "api-resources", "api-versions", "explain", "version", "cluster-info"}
)
KUBECTL_DENIED_OPTIONS = (
    "--raw",
    "--kubeconfig",
    "--context",
    "--server",
    "--token",
    "--as",
    "--as-group",
    "--certificate-authority",
    "--client-certificate",
    "--client-key",
    "--watch",
    "--watch-only",
    "-w",
    "--follow",
    "-f",
)


def _validate_read_only_kubectl(args: list[str]) -> None:
    if not args or args[0] not in KUBECTL_READ_ONLY_COMMANDS:
        raise ValueError("kubectl must use a read-only inspection command")
    for arg in args[1:]:
        if any(arg == option or arg.startswith(f"{option}=") for option in KUBECTL_DENIED_OPTIONS):
            raise ValueError("kubectl credential overrides, raw requests, and streaming are not allowed")


READ_ONLY_SUBCOMMANDS = {
    "git": frozenset({"status", "show", "log", "diff", "grep", "ls-files", "ls-tree", "rev-parse"}),
    "flux": frozenset({"get", "logs", "check", "version", "trace", "tree", "stats"}),
    "helm": frozenset({"list", "status", "get", "history", "show", "version"}),
}
DENIED_ARGUMENTS = {
    "git": ("--ext-diff", "--output", "-o", "-O", "--open-files-in-pager", "--textconv"),
    "find": ("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"),
    "yq": ("-i", "--inplace", "--in-place"),
    "sort": ("-o", "--output", "--compress-program"),
    "helm": ("--output-dir", "--post-renderer", "--kubeconfig", "--kube-context", "--kube-token"),
    "flux": ("--kubeconfig", "--context", "--token"),
    "rg": ("--pre", "--pre-glob", "--search-zip", "-z"),
    "date": ("-s", "--set"),
}
AWK_DENIED = re.compile(r"\b(?:system|getline)\b|[|>]")
SAFETY_PATTERN = re.compile(
    r"\b(?:exec|system|eval|source)\b|(?:/var)?/run/secrets|/proc/|/etc/sentinel|\.ssh/|\.kube/"
)
ENVIRONMENT = ("PATH", "HOME", "TERM", "KUBECONFIG", "GIT_TERMINAL_PROMPT")


def _segments(command: str) -> list[list[str]]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError as exc:
        raise ValueError("invalid shell syntax") from exc
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token == "|":
            segments.append([])
        elif token and set(token) <= set("();<>|&"):
            raise ValueError("shell control operators are not allowed")
        else:
            segments[-1].append(token)
    if any(not segment for segment in segments):
        raise ValueError("empty pipeline segment")
    return segments


def _validate_arguments(arguments: list[str]) -> None:
    binary, rest = arguments[0], arguments[1:]
    if binary == "kubectl":
        _validate_read_only_kubectl(rest)
        return
    if binary in READ_ONLY_SUBCOMMANDS and (not rest or rest[0] not in READ_ONLY_SUBCOMMANDS[binary]):
        raise ValueError(f"{binary} must use a read-only inspection command")
    denied = DENIED_ARGUMENTS.get(binary, ())
    for argument in rest:
        option = argument.split("=", 1)[0]
        if option in denied or (option.startswith("-") and not option.startswith("--") and option[:2] in denied):
            raise ValueError(f"{binary} argument is not allowed: {option}")
    if binary == "awk" and any(AWK_DENIED.search(argument) for argument in rest):
        raise ValueError("awk programs cannot run commands or write output")
    if binary == "uniq" and len([argument for argument in rest if not argument.startswith("-")]) > 1:
        raise ValueError("uniq cannot write an output file")


def validate_command(command: str, allowed_binaries: Iterable[str]) -> list[list[str]]:
    if not command or len(command) > MAX_COMMAND_LENGTH:
        raise ValueError(f"command must be between 1 and {MAX_COMMAND_LENGTH} characters")
    if SAFETY_PATTERN.search(command):
        raise ValueError("credential paths and program execution are not allowed")
    allowed = set(allowed_binaries)
    segments = _segments(command)
    for arguments in segments:
        if arguments[0] not in allowed:
            raise ValueError(f"command must use approved read-only binaries: {sorted(allowed)}")
        _validate_arguments(arguments)
    return segments


def _tail(output, limit: int) -> str:
    size = output.seek(0, os.SEEK_END)
    start = max(0, size - limit)
    output.seek(start)
    tail = output.read()
    return tail.decode(errors="replace")


def execute_pipeline(
    segments: list[list[str]],
    timeout_seconds: float,
    cwd: str | Path | None,
    max_output_bytes: int,
) -> dict[str, Any]:
    environment = {name: os.environ[name] for name in ENVIRONMENT if name in os.environ}
    processes: list[subprocess.Popen] = []
    deadline = time.monotonic() + timeout_seconds
    with tempfile.TemporaryFile() as output_file, tempfile.TemporaryFile() as error_file:
        previous_stdout = None
        try:
            for index, arguments in enumerate(segments):
                process = subprocess.Popen(
                    arguments,
                    stdin=previous_stdout if previous_stdout is not None else subprocess.DEVNULL,
                    stdout=output_file if index == len(segments) - 1 else subprocess.PIPE,
                    stderr=error_file,
                    cwd=cwd,
                    env=environment,
                )
                processes.append(process)
                if previous_stdout is not None:
                    previous_stdout.close()
                previous_stdout = process.stdout
            for process in reversed(processes):
                now = time.monotonic()
                remaining = max(0, deadline - now)
                process.wait(timeout=remaining)
        except BaseException:
            if previous_stdout is not None:
                previous_stdout.close()
            for process in processes:
                if process.poll() is None:
                    process.kill()
            for process in processes:
                process.wait()
            raise
        exit_code = next((process.returncode for process in processes if process.returncode), 0)
        stdout = _tail(output_file, max_output_bytes)
        stderr = _tail(error_file, max_output_bytes)
    return {"exit_code": exit_code, "stdout": stdout, "stderr": stderr}
