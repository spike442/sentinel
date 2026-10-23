from sentinel.api.domains.domain import ConsoleDomain
from sentinel.api.domains.sre.domain import SreDomain

DOMAINS: tuple[ConsoleDomain, ...] = (SreDomain(),)
