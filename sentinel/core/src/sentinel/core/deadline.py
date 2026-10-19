from datetime import UTC, datetime, timedelta


class RunTimedOut(TimeoutError):
    pass


def deadline_after(start: datetime, seconds: int) -> datetime:
    duration = timedelta(seconds=seconds)
    return start + duration


def remaining_seconds(deadline: datetime) -> float:
    now = datetime.now(UTC)
    left = deadline - now
    seconds = left.total_seconds()
    if seconds <= 0:
        raise RunTimedOut("the run passed its deadline")
    return seconds
