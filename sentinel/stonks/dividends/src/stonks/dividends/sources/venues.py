from collections.abc import Mapping
from datetime import date, timedelta

import exchange_calendars
from stonks.dividends.domain.models import Venue


class ListingVenues:
    def __init__(self, venues: Mapping[str, Venue], days_ahead: int):
        self.venues = venues
        self.days_ahead = days_ahead

    def sessions(self, suffix: str, trade_date: date) -> frozenset[date]:
        venue = self.venues.get(suffix)
        if venue is None:
            return frozenset()
        start = trade_date - timedelta(days=31)
        end = trade_date + timedelta(days=self.days_ahead)
        first = start.isoformat()
        last = end.isoformat()
        calendar = exchange_calendars.get_calendar(venue.mic, start=first, end=last)
        return frozenset(session.date() for session in calendar.sessions)

    def filing_domains(self, suffix: str) -> frozenset[str]:
        venue = self.venues.get(suffix)
        return venue.filing_domains if venue else frozenset()
