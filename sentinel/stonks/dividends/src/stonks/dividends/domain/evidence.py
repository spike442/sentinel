import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from urllib.parse import urlsplit

MIN_QUOTE_CHARS = 20
TRANSLATED = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
DAY_SUFFIX = r"(?:st|nd|rd|th|er|e|\.)?"


def normalized(text: str) -> str:
    composed = unicodedata.normalize("NFKC", text)
    translated = composed.translate(TRANSLATED)
    lowered = translated.casefold()
    return " ".join(lowered.split())


def unaccented(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def quote_found(quote: str, page_text: str) -> bool:
    wanted = normalized(quote)
    if len(wanted) < MIN_QUOTE_CHARS:
        return False
    page = normalized(page_text)
    return wanted in page


def host_of(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").casefold()
    return host.removeprefix("www.")


def under_domain(host: str, domains: Iterable[str]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def name_tokens(name: str, stopwords: frozenset[str]) -> set[str]:
    plain = unaccented(name)
    folded = plain.casefold()
    words = re.split(r"[^0-9a-z]+", folded)
    return {word for word in words if len(word) >= 4 and word not in stopwords}


def issuer_host(host: str, name: str, stopwords: frozenset[str]) -> bool:
    labels = host.split(".")
    joined = "".join(labels[:-1])
    registrable = joined.replace("-", "")
    tokens = name_tokens(name, stopwords)
    return any(token in registrable for token in tokens)


def date_patterns(day: date, month_names: Mapping[int, Sequence[str]]) -> list[str]:
    patterns = [
        rf"\b0?{day.day}[./-]0?{day.month}[./-]{day.year}\b",
        rf"\b{day.year}-{day.month:02d}-{day.day:02d}\b",
    ]
    for month in month_names[day.month]:
        lowered = month.casefold()
        plain = unaccented(lowered)
        name = re.escape(plain)
        patterns.append(rf"\b0?{day.day}{DAY_SUFFIX}\s+(?:de\s+|of\s+)?{name}")
        patterns.append(rf"\b{name}\.?\s+0?{day.day}{DAY_SUFFIX}\b")
    return patterns


def mentions_date(text: str, day: date, month_names: Mapping[int, Sequence[str]]) -> bool:
    lowered = normalized(text)
    plain = unaccented(lowered)
    patterns = date_patterns(day, month_names)
    return any(re.search(pattern, plain) for pattern in patterns)


def mentions_amount(text: str, amount: float) -> bool:
    numbers = NUMBER.findall(text)
    values = [float(number.replace(",", ".")) for number in numbers]
    return any(abs(value - amount) < 1e-9 for value in values)
