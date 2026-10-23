from pathlib import Path

from sentinel.core.secrets import contains_secret


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
