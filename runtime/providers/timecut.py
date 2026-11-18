"""Time rules shared by the study dataset build and its providers (spec 006)."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
FRIDAY = 4
CLAMP_NOTE = "Note: dates were limited to the data available on {day}."
LOOKBACK_NOTE = "Note: dates start at {day}, the earliest data available."


@dataclass(frozen=True)
class Record:
    id: str
    public_at: datetime
    source: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class ClampResult:
    start: date
    end: date
    window_end: datetime
    notes: tuple[str, ...]
    miss_reason: str | None


def format_instant(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_instant(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _midnight_after(day: date) -> datetime:
    following = datetime.combine(day + timedelta(days=1), time.min, NEW_YORK)
    return following.astimezone(timezone.utc)


def study_dates(start: date, end: date, trading_days: Sequence[date]) -> list[date]:
    """Return each Friday in range, or the last session before a closed Friday."""
    sessions = sorted(set(trading_days))
    dates = []
    friday = start + timedelta(days=(FRIDAY - start.weekday()) % 7)
    while friday <= end:
        monday = friday - timedelta(days=FRIDAY)
        index = bisect_right(sessions, friday) - 1
        if index >= 0 and sessions[index] >= monday:
            dates.append(sessions[index])
        friday += timedelta(days=7)
    return dates


def cutoff_for(evaluation_date: date, trading_days: Sequence[date]) -> datetime:
    """Return midnight New York time at the end of the last session before D."""
    sessions = sorted(set(trading_days))
    index = bisect_left(sessions, evaluation_date)
    if index == 0:
        raise ValueError("No trading day precedes the evaluation date")
    return _midnight_after(sessions[index - 1])


def admit(public_at: datetime, cutoff: datetime) -> bool:
    return public_at <= cutoff


def public_at_from_date(day: date) -> datetime:
    closing = datetime.combine(day, time(23, 59, 59), NEW_YORK)
    return closing.astimezone(timezone.utc)


def last_admitted_date(cutoff: datetime) -> date:
    return (cutoff.astimezone(NEW_YORK) - timedelta(seconds=1)).date()


def clamp_date(day: date, cutoff: datetime) -> tuple[date, tuple[str, ...]]:
    """Clamp a single `curr_date` argument to the last admitted date."""
    last = last_admitted_date(cutoff)
    if day <= last:
        return day, ()
    return last, (CLAMP_NOTE.format(day=last.isoformat()),)


def clamp(
    start: date, end: date, cutoff: datetime, lookback_days: int | None
) -> ClampResult:
    """Limit a requested inclusive New York date window to what a copy can answer."""
    if start > end:
        return ClampResult(start, end, cutoff, (), "invalid_window")
    last = last_admitted_date(cutoff)
    if start > last:
        return ClampResult(start, end, cutoff, (), "after_cutoff")
    notes = []
    miss_reason = None
    if end > last:
        end = last
        notes.append(CLAMP_NOTE.format(day=last.isoformat()))
    if lookback_days is not None:
        first = (cutoff.astimezone(NEW_YORK) - timedelta(days=lookback_days)).date()
        if start < first:
            start = first
            miss_reason = "before_lookback"
            notes.append(LOOKBACK_NOTE.format(day=first.isoformat()))
    window_end = min(cutoff, _midnight_after(end))
    return ClampResult(start, end, window_end, tuple(notes), miss_reason)
