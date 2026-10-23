from collections.abc import Collection, Mapping

from stonks.ingest.domain.models import Constituent, Country, Rejection, Selection


def rejection_reason(
    constituent: Constituent, seen: Collection[str], countries: Collection[str], excluded: Collection[str]
) -> str | None:
    if constituent.isin in seen:
        return "duplicate_isin"
    if constituent.weight <= 0:
        return "not_held"
    if constituent.isin in excluded:
        return "pea_excluded"
    if constituent.country not in countries:
        return "pea_country"
    return None


def select_pea(constituents: list[Constituent], countries: Collection[str], excluded: Collection[str]) -> Selection:
    eligible = []
    rejections = []
    seen = set()
    for constituent in constituents:
        reason = rejection_reason(constituent, seen, countries, excluded)
        seen.add(constituent.isin)
        if reason is None:
            eligible.append(constituent)
        else:
            rejected = Rejection(constituent.isin, constituent.name, reason)
            rejections.append(rejected)
    return Selection(eligible=eligible, rejections=rejections)


def pea_countries(countries: Mapping[str, Country]) -> frozenset[str]:
    return frozenset(code for code, country in countries.items() if country.pea)
