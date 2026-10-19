from pathlib import PurePosixPath

from sentinel.core.contracts.changes import ProposedChange
from sentinel.core.secrets import contains_secret


def rejection(changes: list[ProposedChange]) -> str | None:
    for change in changes:
        path = change.file_path
        parts = PurePosixPath(path)
        if not path or parts.is_absolute() or ".." in parts.parts:
            return f"Change path is not repository-relative: {path!r}."
        if contains_secret(change.content):
            return f"Change content looks like credential material: {path}."
    return None
