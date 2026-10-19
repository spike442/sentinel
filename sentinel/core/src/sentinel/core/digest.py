import json
from hashlib import sha256
from typing import Any


def json_digest(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True)
    encoded = serialized.encode()
    return sha256(encoded).hexdigest()


def text_digest(text: str) -> str:
    encoded = text.encode()
    return sha256(encoded).hexdigest()
