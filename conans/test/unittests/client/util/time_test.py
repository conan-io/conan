import datetime
import unittest

from conans.util.dates import from_timestamp_to_iso8601, from_iso8601_to_datetime, valid_iso8601


class TimeTest(unittest.TestCase):

    def time_conversions_test(self):
        timestamp = "1547138099"
        iso = from_timestamp_to_iso8601(timestamp)
        self.assertEquals(iso, "2019-01-10T16:34:59Z")

        dt = from_iso8601_to_datetime(iso)
        expected = datetime.datetime(year=2019, month=1, day=10, hour=16, minute=34, second=59)
        self.assertEquals(dt, expected)

    def validation_test(self):
        self.assertFalse(valid_iso8601("1547138099"))
        self.assertTrue(valid_iso8601("2019-01-10T16:34:59Z"))
