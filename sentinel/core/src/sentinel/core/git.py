from collections.abc import Callable
from pathlib import Path


def sync_checkout(git: Callable[[list[str]], str], path: Path, remote: str, branch: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if (path / ".git").is_dir():
        git(["-C", str(path), "remote", "set-url", "origin", remote])
        git(["-C", str(path), "fetch", "--prune", "origin", branch])
        git(["-C", str(path), "checkout", "-B", branch, f"origin/{branch}"])
        git(["-C", str(path), "reset", "--hard", f"origin/{branch}"])
        return
    git(["clone", "--single-branch", "--branch", branch, remote, str(path)])
