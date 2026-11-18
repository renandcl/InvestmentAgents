import unittest
from datetime import date, datetime, timedelta, timezone

from runtime.providers.timecut import (
    admit,
    clamp,
    clamp_date,
    cutoff_for,
    format_instant,
    public_at_from_date,
    study_dates,
)

WEEK = [date(2026, 3, 30), date(2026, 3, 31), date(2026, 4, 1), date(2026, 4, 2)]


class TimeRuleTests(unittest.TestCase):
    def test_closed_friday_snaps_to_last_session(self) -> None:
        sessions = [*WEEK, date(2026, 4, 6), date(2026, 4, 10)]
        dates = study_dates(date(2026, 3, 30), date(2026, 4, 10), sessions)
        self.assertEqual(dates, [date(2026, 4, 2), date(2026, 4, 10)])

    def test_cutoff_is_midnight_new_york_across_daylight_saving(self) -> None:
        winter = cutoff_for(date(2026, 1, 9), [date(2026, 1, 8), date(2026, 1, 9)])
        summer = cutoff_for(date(2026, 7, 10), [date(2026, 7, 9), date(2026, 7, 10)])
        self.assertEqual(format_instant(winter), "2026-01-09T05:00:00Z")
        self.assertEqual(format_instant(summer), "2026-07-10T04:00:00Z")

    def test_record_at_cutoff_is_admitted_and_one_second_later_is_not(self) -> None:
        cutoff = datetime(2026, 1, 9, 5, tzinfo=timezone.utc)
        self.assertTrue(admit(cutoff, cutoff))
        self.assertFalse(admit(cutoff + timedelta(seconds=1), cutoff))

    def test_date_only_record_of_last_session_is_admitted(self) -> None:
        cutoff = cutoff_for(date(2026, 1, 9), [date(2026, 1, 8), date(2026, 1, 9)])
        self.assertTrue(admit(public_at_from_date(date(2026, 1, 8)), cutoff))
        self.assertFalse(admit(public_at_from_date(date(2026, 1, 9)), cutoff))

    def test_clamp_limits_end_and_keeps_inclusive_new_york_dates(self) -> None:
        cutoff = datetime(2026, 1, 9, 5, tzinfo=timezone.utc)
        result = clamp(date(2026, 1, 5), date(2030, 1, 1), cutoff, None)
        self.assertEqual(result.end, date(2026, 1, 8))
        self.assertEqual(result.window_end, cutoff)
        self.assertEqual(
            result.notes,
            ("Note: dates were limited to the data available on 2026-01-08.",),
        )
        inside = clamp(date(2026, 1, 5), date(2026, 1, 6), cutoff, None)
        self.assertEqual(
            inside.window_end, datetime(2026, 1, 7, 5, tzinfo=timezone.utc)
        )
        self.assertEqual(inside.notes, ())

    def test_clamp_reports_each_unanswerable_window(self) -> None:
        cutoff = datetime(2026, 1, 9, 5, tzinfo=timezone.utc)
        after = clamp(date(2026, 1, 9), date(2026, 1, 10), cutoff, None)
        reversed_window = clamp(date(2026, 1, 6), date(2026, 1, 5), cutoff, None)
        early = clamp(date(2025, 12, 1), date(2026, 1, 8), cutoff, 7)
        self.assertEqual(after.miss_reason, "after_cutoff")
        self.assertEqual(reversed_window.miss_reason, "invalid_window")
        self.assertEqual(early.miss_reason, "before_lookback")
        self.assertEqual(early.start, date(2026, 1, 2))

    def test_curr_date_clamps_to_last_admitted_date(self) -> None:
        cutoff = datetime(2026, 1, 9, 5, tzinfo=timezone.utc)
        day, notes = clamp_date(date(2026, 1, 9), cutoff)
        self.assertEqual(day, date(2026, 1, 8))
        self.assertEqual(len(notes), 1)
        self.assertEqual(clamp_date(date(2026, 1, 7), cutoff), (date(2026, 1, 7), ()))


if __name__ == "__main__":
    unittest.main()
