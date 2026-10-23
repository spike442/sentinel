import re
from collections.abc import Sequence


def focus_text(text: str, terms: Sequence[str], window: int, limit: int) -> str:
    lowered = text.casefold()
    spans: list[list[int]] = []
    for term in terms:
        folded = term.casefold()
        pattern = re.escape(folded)
        for match in re.finditer(pattern, lowered):
            start = max(match.start() - window, 0)
            end = min(match.end() + window, len(text))
            spans.append([start, end])
    if not spans:
        return text[:limit]
    spans.sort()
    merged = [spans[0]]
    for start, end in spans[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    excerpts = [text[start:end] for start, end in merged]
    joined = "\n...\n".join(excerpts)
    return joined[:limit]
